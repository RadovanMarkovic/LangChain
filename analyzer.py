import os
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from github_client import RepositoryFile


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


def analyze_repository(
    repository: dict[str, Any],
    files: list[RepositoryFile],
    provider: str = "openai",
    model: str | None = None,
    base_url: str | None = None,
) -> str:
    normalized_provider = provider.strip().lower()
    llm = _build_llm(provider=normalized_provider, model=model, base_url=base_url)
    chain = SUMMARY_PROMPT | llm | StrOutputParser()

    return chain.invoke(
        {
            "metadata": _format_metadata(repository),
            "files": _format_files(files),
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
        )

    raise RuntimeError(
        f"Unsupported provider: {provider}. Supported providers are: openai, ollama."
    )


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


def _format_files(files: list[RepositoryFile]) -> str:
    # Jasno odvaja svaki izabrani fajl da model lakse poveze zapazanja sa fajlovima.
    if not files:
        return "No important files were found or fetched."

    sections: list[str] = []
    for file in files:
        truncated_note = " (truncated)" if file.truncated else ""
        sections.append(
            f"--- FILE: {file.path}{truncated_note} ---\n"
            f"{file.content.strip()}\n"
        )
    return "\n".join(sections)
