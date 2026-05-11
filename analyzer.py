import json
import os
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from github_client import RepositoryFile

DEFAULT_OLLAMA_CONTEXT_CHARS = 24_000
DEFAULT_OLLAMA_NUM_CTX = 8192


# Prompt template koji modelu objasnjava kakav summary treba da napravi.
SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a senior software engineer who explains repositories clearly and briefly. "
            "Use only the repository metadata and selected file contents provided by the user. "
            "If something is uncertain, say so.",
        ),
        (
            "user",
            """Analyze this GitHub repository and produce a short Markdown summary.

Include these sections:
- What the project does
- Technologies used
- Likely purpose
- Important observations from selected files

Keep the answer concise and practical.

Repository metadata:
{metadata}

Selected files:
{files}
""",
        ),
    ]
)

OLLAMA_SUMMARY_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a precise repository summarizer. "
            "Use only the repository metadata and selected file contents provided by the user. "
            "Do not give advice, recommendations, warnings, code improvements, refactors, reviews, or rewritten code. "
            "Do not invent files, frameworks, endpoints, or behavior that are not clearly present in the input. "
            "If something is uncertain, say it is uncertain. "
            "Return only valid JSON with no prose before or after it.",
        ),
        (
            "user",
            """Analyze this GitHub repository and produce a structured summary.

Rules:
- Return only a JSON object.
- Do not return Markdown.
- Do not include suggestions or improvements.
- Do not include sample code.
- Keep every field concise and factual.
- Do not include suggestions or improvements.
- If the repository content is insufficient for a claim, explicitly say it is uncertain.

Use this exact JSON schema:
{{
  "what_the_project_does": "string",
  "technologies_used": ["string"],
  "likely_purpose": "string",
  "important_observations": ["string"]
}}

Repository metadata:
{metadata}

Selected files:
{files}
""",
        ),
    ]
)


def analyze_repository(
    repository: dict[str, Any],
    files: list[RepositoryFile],
    provider: str = "openai",
    model: str | None = None,
    base_url: str | None = None,
) -> str:
    normalized_provider = provider.strip().lower()
    llm = _build_llm(provider=normalized_provider, model=model, base_url=base_url)
    metadata = _format_metadata(repository)
    files_text = _format_files(files)

    if normalized_provider == "ollama":
        files_text = _format_files(
            files,
            max_total_chars=_get_int_env(
                "OLLAMA_CONTEXT_CHARS",
                DEFAULT_OLLAMA_CONTEXT_CHARS,
            ),
        )
        chain = OLLAMA_SUMMARY_PROMPT | llm | StrOutputParser()
        raw_output = chain.invoke(
            {
                "metadata": metadata,
                "files": files_text,
            }
        )
        return _render_ollama_summary(_parse_ollama_json(raw_output))

    chain = SUMMARY_PROMPT | llm | StrOutputParser()
    return chain.invoke(
        {
            "metadata": metadata,
            "files": files_text,
        }
    )


def _build_llm(
    provider: str,
    model: str | None = None,
    base_url: str | None = None,
) -> Any:
    normalized_provider = provider.strip().lower()

    if normalized_provider == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it before running with provider=openai."
            )

        return ChatOpenAI(
            model=model or os.getenv("LLM_MODEL", "gpt-4o-mini"),
            temperature=0.2,
        )

    if normalized_provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as error:
            raise RuntimeError(
                "langchain-ollama is not installed. Install it with: pip install langchain-ollama"
            ) from error

        return ChatOllama(
            model=model or os.getenv("LLM_MODEL", "llama3.2"),
            temperature=0.0,
            base_url=base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            format="json",
            num_ctx=_get_int_env("OLLAMA_NUM_CTX", DEFAULT_OLLAMA_NUM_CTX),
        )

    raise RuntimeError(
        f"Unsupported provider: {provider}. Supported providers are: openai, ollama."
    )


def _parse_ollama_json(raw_output: str) -> dict[str, Any]:
    cleaned = raw_output.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1]).strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

    parsed = _load_json_object(cleaned)

    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama returned invalid summary data.")

    return parsed


def _load_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError(
                "Ollama returned a response that was not valid JSON. Try rerunning with a smaller --max-files value, increasing OLLAMA_NUM_CTX, or switching models."
            )

        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Ollama returned a response that was not valid JSON. Try rerunning with a smaller --max-files value, increasing OLLAMA_NUM_CTX, or switching models."
            ) from error


def _render_ollama_summary(summary: dict[str, Any]) -> str:
    what_the_project_does = _normalize_text(
        summary.get("what_the_project_does"),
        fallback="Uncertain based on the selected files.",
    )
    technologies_used = _normalize_list(
        summary.get("technologies_used"),
        fallback="Uncertain based on the selected files.",
    )
    likely_purpose = _normalize_text(
        summary.get("likely_purpose"),
        fallback="Uncertain based on the selected files.",
    )
    important_observations = _normalize_list(
        summary.get("important_observations"),
        fallback="Uncertain based on the selected files.",
    )

    return (
        "## What the project does\n"
        f"{what_the_project_does}\n\n"
        "## Technologies used\n"
        f"{_format_bullets(technologies_used)}\n\n"
        "## Likely purpose\n"
        f"{likely_purpose}\n\n"
        "## Important observations from selected files\n"
        f"{_format_bullets(important_observations)}"
    )


def _normalize_text(value: Any, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _normalize_list(value: Any, fallback: str) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        if items:
            return items
    return [fallback]


def _format_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _format_metadata(repository: dict[str, Any]) -> str:
    # Pretvara najkorisnije GitHub metadata podatke u kompaktan prompt tekst.
    fields = {
        "Name": repository.get("full_name"),
        "Description": repository.get("description") or "No description provided",
        "Default branch": repository.get("default_branch"),
        "Primary language": repository.get("language") or "Unknown",
        "Stars": repository.get("stargazers_count"),
        "Forks": repository.get("forks_count"),
        "Open issues": repository.get("open_issues_count"),
        "URL": repository.get("html_url"),
    }
    return "\n".join(f"- {key}: {value}" for key, value in fields.items())


def _get_int_env(name: str, fallback: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return fallback

    try:
        value = int(raw_value)
    except ValueError:
        return fallback

    return value if value > 0 else fallback


def _format_files(
    files: list[RepositoryFile],
    max_total_chars: int | None = None,
) -> str:
    # Jasno odvaja svaki izabrani fajl da model lakse poveze zapazanja sa fajlovima.
    if not files:
        return "No important files were found or fetched."

    sections: list[str] = []
    used_chars = 0
    for file in files:
        truncated_note = " (truncated)" if file.truncated else ""
        section = f"--- FILE: {file.path}{truncated_note} ---\n{file.content.strip()}\n"

        if max_total_chars is not None and used_chars + len(section) > max_total_chars:
            remaining_chars = max_total_chars - used_chars
            if remaining_chars <= 200:
                sections.append(
                    "\n[Additional selected files were omitted because the Ollama context budget was reached.]\n"
                )
                break

            section = (
                section[:remaining_chars]
                + "\n\n[Repository context truncated for Ollama analysis]\n"
            )
            sections.append(section)
            break

        sections.append(section)
        used_chars += len(section)
    return "\n".join(sections)
