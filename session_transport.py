from typing import TYPE_CHECKING

from _repo_bootstrap import alias_module

if TYPE_CHECKING:
    from codesys_api.session_transport import (
        TransportExecutionContext,
        TransportRequest,
        build_primary_script_transport,
    )

    __all__ = [
        "TransportRequest",
        "TransportExecutionContext",
        "build_primary_script_transport",
    ]
else:
    alias_module(__name__, "codesys_api.session_transport")
