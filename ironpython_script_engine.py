from typing import TYPE_CHECKING

from _repo_bootstrap import alias_module

if TYPE_CHECKING:
    from codesys_api.ironpython_script_engine import *  # noqa: F401,F403
else:
    alias_module(__name__, "codesys_api.ironpython_script_engine")
