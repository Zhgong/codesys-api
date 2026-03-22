# Internal Release Flow

## Summary

The repository now supports repeatable internal releases based on wheel and sdist artifacts.

This flow is for **internal distribution only**:

- no PyPI upload
- no installer generation
- no cross-platform packaging promises

For public-package readiness, see [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md).

GitHub Actions now mirrors this release path:

- `.github/workflows/ci.yml`
- `.github/workflows/release-build.yml`
- `.github/workflows/publish.yml`
- `.github/workflows/verify-published-package.yml`

## Version Source

The single version source is `pyproject.toml`:

- `project.version`

Release artifacts must match that version:

- `dist/codesys_tools-<version>-*.whl`
- `dist/codesys_tools-<version>.tar.gz`

## Release Checklist

Run from the repository root:

```powershell
python scripts\run_baseline.py
python scripts\build_release.py
```

Then verify the wheel in a clean virtual environment:

```powershell
python -m venv C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\python.exe -m pip install --upgrade pip
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\python.exe -m pip install dist\codesys_tools-*.whl
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\codesys-tools.exe --help
C:\Users\vboxuser\Desktop\codesys-tools-wheel-smoke\Scripts\codesys-tools-server.exe --help
```

GitHub-hosted equivalent:

- CI on `push` / `pull_request` to `master`
- manual `Release Build` workflow for artifact production
- manual `Publish Package` workflow for TestPyPI or PyPI
- manual `Verify Published Package` workflow for clean install verification from TestPyPI or PyPI

Installed package validation must also confirm:

- packaged `PERSISTENT_SESSION.py` resolves
- packaged `ScriptLib/` resolves
- default API key path remains under `%APPDATA%\codesys-api\api_keys.json`

## Internal Distribution

Recommended internal handoff bundle:

- wheel from `dist/`
- matching sdist from `dist/`
- commit hash
- short release note entry

Install from a wheel:

```powershell
python -m pip install dist\codesys_tools-*.whl
```

Upgrade an existing installation:

```powershell
python -m pip install --upgrade dist\codesys_tools-*.whl
```

## Release Record

For each internal release, record:

- version
- commit hash
- release date
- artifact filenames
- baseline result
- wheel smoke result

Append release summaries to [RELEASE_NOTES.md](RELEASE_NOTES.md).

## First Public Publication Order

1. Confirm `CI` is green on `master`
2. Run the manual `Release Build` workflow
3. Run the manual `Publish Package` workflow with `target=testpypi`
4. Run the manual `Verify Published Package` workflow with `target=testpypi`
5. Run the manual `Publish Package` workflow with `target=pypi`
6. Run the manual `Verify Published Package` workflow with `target=pypi`
