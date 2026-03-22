# Release Notes

## Unreleased

### Current Internal Release Candidate

- Commit: fill this in when cutting the internal release
- Baseline gate: `170 passed, 8 skipped`
- Static gate: `mypy` passes with no issues in `60` source files
- Packaging gate:
  - `python scripts\build_release.py` succeeds
  - wheel and sdist are produced
  - clean wheel-install smoke passes
- Installed entrypoints verified:
  - `codesys-tools`
  - `codesys-tools-server`
- Installed packaged assets verified:
  - `PERSISTENT_SESSION.py`
  - `ScriptLib/`
