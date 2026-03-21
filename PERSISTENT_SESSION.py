"""
CODESYS Persistent Session compatibility wrapper.

This wrapper keeps the historical repo-root entrypoint available while the
authoritative IronPython script now lives under src/codesys_api/assets.
"""

import os


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(
    SCRIPT_DIR,
    "src",
    "codesys_api",
    "assets",
    "PERSISTENT_SESSION.py",
)


handle = open(TARGET_SCRIPT, "rb")
try:
    source = handle.read()
finally:
    handle.close()

globals_dict = globals()
globals_dict["__file__"] = TARGET_SCRIPT
exec compile(source, TARGET_SCRIPT, "exec") in globals_dict, globals_dict
