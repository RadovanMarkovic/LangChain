import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import requests

from analyzer import analyze_repository
from github_client import GitHubClient


def main() -> None:
    # Ucitava API kljuceve i opcioni model iz lokalnog .env fajla.
    load_dotenv()

    # Cita argumente iz terminala ili trazi repository URL od korisnika.
    args = parse_args()
    repository_url = args.repository_url or input("GitHub repository URL: ").strip()

    try:
        # Preuzima metadata repozitorijuma i mali skup vaznih fajlova.
        client = GitHubClient()
        repository = client.get_repository(repository_url)
        files = client.fetch_important_files(
            repository,
            max_files=args.max_files,
            max_chars_per_file=args.max_chars_per_file,
        )

        if not files:
            print("No important files were found to analyze.")
            return

        print(f"Repository: {repository['full_name']}")
        print("Selected files:")
        for file in files:
            print(f"- {file.path}")

        # Salje izabrani kontekst LangChain-u da napravi summary.
        print("\nAnalyzing repository with LangChain...\n")
        summary = analyze_repository(
            repository,
            files,
            provider=args.provider,
            model=args.model,
            base_url=args.base_url,
        )

        # Cuva isti summary koji se ispisuje u terminalu.
        output_path = Path(args.output)
        output_path.write_text(summary, encoding="utf-8")

        print(summary)
        print(f"\nSaved summary to: {output_path.resolve()}")

    except (ValueError, RuntimeError, requests.RequestException) as error:
        print(f"Error: {error}")


def parse_args() -> argparse.Namespace:
    # Definise jednostavan CLI interfejs za ovu MVP aplikaciju.
    parser = argparse.ArgumentParser(
        description="Analyze a GitHub repository with a simple LangChain agent."
    )
    parser.add_argument(
        "repository_url",
        nargs="?",
        help="GitHub repository URL, for example https://github.com/langchain-ai/langchain",
    )
    parser.add_argument(
        "--output",
        default="repository_summary.md",
        help="Path where the Markdown summary will be saved.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=12,
        help="Maximum number of important files to read from the repository.",
    )
    parser.add_argument(
        "--max-chars-per-file",
        type=int,
        default=6_000,
        help="Maximum characters to read from each selected repository file.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name for the selected provider. Defaults to LLM_MODEL or a provider-specific fallback.",
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("LLM_PROVIDER", "openai"),
        choices=("openai", "ollama"),
        help="LLM provider to use. Defaults to LLM_PROVIDER or openai.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Optional base URL for providers such as Ollama. Defaults to OLLAMA_BASE_URL or http://localhost:11434 for Ollama.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
