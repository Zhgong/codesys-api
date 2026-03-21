# Release Notes

## Unreleased

### Current Internal Release Candidate

- Commit: fill this in when cutting the internal release
- Baseline gate: `167 passed, 8 skipped`
- Static gate: `mypy` passes with no issues in `58` source files
- Packaging gate:
  - `python scripts\build_release.py` succeeds
  - wheel and sdist are produced
  - clean wheel-install smoke passes
- Installed entrypoints verified:
  - `codesys`
  - `codesys-server`
- Installed packaged assets verified:
  - `PERSISTENT_SESSION.py`
  - `ScriptLib/`
