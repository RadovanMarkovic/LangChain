import argparse
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
        files = client.fetch_important_files(repository, max_files=args.max_files)

        if not files:
            print("No important files were found to analyze.")
            return

        print(f"Repository: {repository['full_name']}")
        print("Selected files:")
        for file in files:
            print(f"- {file.path}")

        # Salje izabrani kontekst LangChain-u da napravi summary.
        print("\nAnalyzing repository with LangChain...\n")
        summary = analyze_repository(repository, files, model=args.model)

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
        default=8,
        help="Maximum number of important files to read from the repository.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI chat model name. Defaults to LLM_MODEL or gpt-4o-mini.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
