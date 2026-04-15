# GitHub Repository AI Analyzer

Jednostavna MVP Python aplikacija koja analizira GitHub repozitorijum.

Aplikacija prima GitHub repository URL, preko GitHub API-ja procita osnovne informacije i nekoliko vaznih fajlova, zatim koristi LangChain i OpenAI model da napravi kratak summary projekta.

Rezultat se:

- ispisuje u terminalu
- cuva u Markdown fajl

## Struktura projekta

```text
langchain/
|-- .env
|-- .gitignore
|-- analyzer.py
|-- github_client.py
|-- main.py
|-- README.md
`-- requirements.txt
```

Lokalno se posle setup-a moze pojaviti i:

```text
langchain/
|-- .venv/
|-- __pycache__/
`-- repository_summary.md
```

## Sta aplikacija cita iz repozitorijuma

Aplikacija ne cita ceo repozitorijum. Cita najvise nekoliko vaznih fajlova, na primer:

- `README.md`
- `Dockerfile`
- `docker-compose.yml`
- `package.json`
- `requirements.txt`
- `pyproject.toml`
- `.env.example`
- jedan ili dva source/config fajla kao `main.py`, `app.py`, `index.ts`

Podrazumevano cita najvise 8 fajlova.

## 1. Napravi virtualno okruzenje

```bash
python -m venv .venv
```

## 2. Aktiviraj virtualno okruzenje

Izaberi komandu za terminal koji koristis.

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

Ako PowerShell blokira aktivaciju, pokreni:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Git Bash na Windows-u

```bash
source .venv/Scripts/activate
```

Ne koristi ovu komandu na Windows-u:

```bash
source .venv/bin/activate
```

Ta putanja je za Linux/macOS. Na Windows-u virtual environment koristi `.venv/Scripts`.

### Command Prompt

```cmd
.venv\Scripts\activate.bat
```

## 3. Instaliraj dependencies

Kada je virtualno okruzenje aktivirano, pokreni:

```bash
pip install -r requirements.txt
```

## 4. Popuni `.env` fajl

Otvori `.env` i zameni placeholder vrednosti svojim kljucevima:

```env
OPENAI_API_KEY=tvoj_openai_api_key
GITHUB_TOKEN=tvoj_github_token
LLM_MODEL=gpt-4o-mini
```

`OPENAI_API_KEY` je obavezan.

`GITHUB_TOKEN` nije obavezan, ali je preporucen zbog GitHub rate limita.

`LLM_MODEL` je opcionalan. Ako ga ne promenis, koristi se `gpt-4o-mini`.

## 5. Pokreni aplikaciju

Primer:

```bash
python main.py https://github.com/psf/requests
```

Custom output fajl:

```bash
python main.py https://github.com/psf/requests --output requests_summary.md
```

Specifican model preko argumenta:

```bash
python main.py https://github.com/psf/requests --model gpt-4o-mini
```

## 7. Output

Rezultat se ispisuje u terminalu i cuva u:

```text
repository_summary.md
```

Ako koristis `--output`, rezultat se cuva u fajl koji navedes.

