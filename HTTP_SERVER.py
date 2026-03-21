from typing import TYPE_CHECKING

from _repo_bootstrap import alias_module

if TYPE_CHECKING:
    from codesys_api.http_server import *  # noqa: F401,F403
else:
    alias_module(__name__, "codesys_api.http_server")


if __name__ == "__main__":
    from codesys_api.http_server import main

    raise SystemExit(main())
