import base64
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import requests


GITHUB_API_URL = "https://api.github.com"

# Fajlovi pri vrhu liste imaju veci prioritet kada postoje u repozitorijumu.
IMPORTANT_FILE_PRIORITY = [
    "README.md",
    "readme.md",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "poetry.lock",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    ".env.example",
    "environment.yml",
    "tsconfig.json",
    "vite.config.ts",
    "next.config.js",
]

# Cesta imena source entry-point fajlova koja se proveravaju posle config fajlova.
SOURCE_ENTRYPOINT_NAMES = [
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "index.js",
    "index.ts",
    "app.js",
    "app.ts",
    "App.jsx",
    "App.tsx",
]


@dataclass
class RepositoryFile:
    # Jednostavan objekat za putanju i tekst fajla koji se salje analyzer-u.
    path: str
    content: str
    truncated: bool = False


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        # Koristi jednu session instancu da svi zahtevi imaju iste GitHub headere.
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "langchain-github-repo-analyzer",
            }
        )

        # GITHUB_TOKEN je opcionalan, ali povecava rate limit i omogucava private repo pristup.
        token = token or os.getenv("GITHUB_TOKEN")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def get_repository(self, repository_url: str) -> dict[str, Any]:
        # Pretvara GitHub URL u owner/repo i preuzima metadata repozitorijuma.
        owner, repo = parse_github_url(repository_url)
        return self._get(f"/repos/{owner}/{repo}")

    def fetch_important_files(
        self,
        repository: dict[str, Any],
        max_files: int = 8,
        max_chars_per_file: int = 12_000,
    ) -> list[RepositoryFile]:
        # Prvo cita tree repozitorijuma, zatim bira mali broj korisnih fajlova.
        owner = repository["owner"]["login"]
        repo = repository["name"]
        branch = repository["default_branch"]

        tree = self._get(
            f"/repos/{owner}/{repo}/git/trees/{quote(branch, safe='')}",
            params={"recursive": "1"},
        )
        paths = select_important_paths(tree.get("tree", []), max_files=max_files)

        files: list[RepositoryFile] = []
        for path in paths:
            fetched = self._fetch_file(owner, repo, branch, path, max_chars_per_file)
            if fetched is not None:
                files.append(fetched)

        return files

    def _fetch_file(
        self,
        owner: str,
        repo: str,
        branch: str,
        path: str,
        max_chars: int,
    ) -> RepositoryFile | None:
        # GitHub vraca sadrzaj fajla kao base64, pa ga dekodiramo u tekst.
        encoded_path = quote(path, safe="/")
        data = self._get(
            f"/repos/{owner}/{repo}/contents/{encoded_path}",
            params={"ref": branch},
        )

        if data.get("type") != "file" or data.get("encoding") != "base64":
            return None

        raw = base64.b64decode(data.get("content", ""), validate=False)
        text = raw.decode("utf-8", errors="replace")

        # Skracuje velike fajlove da prompt ostane mali i predvidljiv.
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + "\n\n[File truncated for analysis]\n"

        return RepositoryFile(path=path, content=text, truncated=truncated)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Centralizovan GET helper za GitHub API pozive i ceste greske.
        response = self.session.get(f"{GITHUB_API_URL}{path}", params=params, timeout=30)
        if response.status_code == 404:
            raise ValueError(f"GitHub resource was not found: {path}")
        if response.status_code == 403:
            raise ValueError(
                "GitHub API rate limit or permission error. "
                "Set GITHUB_TOKEN to use an authenticated request."
            )
        response.raise_for_status()
        return response.json()


def parse_github_url(repository_url: str) -> tuple[str, str]:
    # Prihvata i HTTPS URL i SSH GitHub URL format.
    repository_url = repository_url.strip()

    ssh_match = re.match(r"^git@github\.com:([^/]+)/(.+?)(?:\.git)?$", repository_url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    parsed = urlparse(repository_url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError("Please provide a GitHub URL like https://github.com/owner/repo")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("GitHub URL must include both owner and repository name.")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")
    return owner, repo


def select_important_paths(tree_items: list[dict[str, Any]], max_files: int = 8) -> list[str]:
    # Bira fajlove deterministicki: root config, nested config, pa entry-point fajlovi.
    file_paths = sorted(
        item["path"]
        for item in tree_items
        if item.get("type") == "blob" and not _looks_like_generated_or_vendor_file(item["path"])
    )
    path_set = set(file_paths)

    selected: list[str] = []

    # Prvo bira vazne fajlove iz root foldera repozitorijuma.
    for important_name in IMPORTANT_FILE_PRIORITY:
        if important_name in path_set:
            _append_unique(selected, important_name, max_files)
            if len(selected) >= max_files:
                return selected

    # Zatim trazi vazne config fajlove u podfolderima.
    for important_name in IMPORTANT_FILE_PRIORITY:
        if important_name.lower().startswith("readme"):
            continue
        for candidate in _nested_matching_paths(file_paths, important_name):
            _append_unique(selected, candidate, max_files)
            if len(selected) >= max_files:
                return selected

    source_candidates = sorted(
        path
        for path in path_set
        if path.split("/")[-1] in SOURCE_ENTRYPOINT_NAMES
    )
    source_candidates.sort(key=_source_path_score)

    # Dodaje potencijalne ulazne fajlove aplikacije ako jos ima mesta.
    for candidate in source_candidates:
        _append_unique(selected, candidate, max_files)
        if len(selected) >= max_files:
            return selected

    # Nested README fajlovi su korisni, ali tek posle jacih project-level fajlova.
    for candidate in _nested_matching_paths(file_paths, "README.md"):
        _append_unique(selected, candidate, max_files)
        if len(selected) >= max_files:
            return selected

    return selected


def _nested_matching_paths(file_paths: list[str], filename: str) -> list[str]:
    # Daje prednost fajlovima koji su blize root folderu.
    matches = [path for path in file_paths if path.endswith(f"/{filename}")]
    matches.sort(key=lambda path: (path.count("/"), path))
    return matches


def _append_unique(selected: list[str], path: str, max_files: int) -> None:
    if path not in selected and len(selected) < max_files:
        selected.append(path)


def _source_path_score(path: str) -> tuple[int, int, str]:
    # Rangira source foldere pre primera ili duboko ugnjezdenih fajlova.
    preferred_prefixes = ("src/", "app/", "server/", "backend/", "frontend/")
    prefix_score = 0 if path.startswith(preferred_prefixes) else 1
    return prefix_score, path.count("/"), path


def _looks_like_generated_or_vendor_file(path: str) -> bool:
    # Preskace dependencies, build output, cache foldere i generisane fajlove.
    ignored_parts = {
        ".git",
        ".github",
        ".next",
        ".venv",
        "dist",
        "build",
        "coverage",
        "node_modules",
        "vendor",
        "__pycache__",
    }
    return any(part in ignored_parts for part in path.split("/"))
