# Publish Checklist

Use this as the short release checklist for `codesys-tools`.

## Before Publishing

- update `pyproject.toml` version
- update `docs/RELEASE_NOTES.md`
- merge the release commit to `master`
- wait for GitHub `CI` on `master` to pass

## TestPyPI

1. Run `Release Build`
2. Run `Publish Package`
   - `target=testpypi`
3. Run `Verify Published Package`
   - `target=testpypi`
   - `version=<release version>`

## PyPI

Only after TestPyPI verification passes:

1. Run `Publish Package`
   - `target=pypi`
2. Run `Verify Published Package`
   - `target=pypi`
   - `version=<release version>`

## After Publishing

- update `docs/RELEASE_NOTES.md` with:
  - version
  - commit hash
  - release date
  - TestPyPI verification result
  - PyPI verification result
- create and push the git tag

## Notes

- official release flow is GitHub-based
- public Python support is `3.13+`
- release and publish workflows stay pinned to `3.14`
