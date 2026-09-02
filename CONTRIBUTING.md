# Contributing to SupaDL

## Development contract

- Work on one `SUP-` task or a small dependency group at a time.
- Read `README.md`, `docs/architecture.md`, `docs/security.md`, the relevant acceptance
  criteria, and nearby tests before editing.
- Do not implement future milestones opportunistically.
- Keep the domain and application layers independent of PySide6 and infrastructure.
- Never disable TLS verification, log secrets, silently overwrite user files, or trust a
  server filename as a path.
- Add or update tests for changed behavior and keep the repository runnable.

## Local workflow

Create and activate a Python 3.14 virtual environment, then install the development group:

```powershell
python -m pip install -e ".[dev]"
```

Before submitting a change, run:

```powershell
.\tools\check.ps1
```

Report the changed files, commands and results, and any remaining limitations.

