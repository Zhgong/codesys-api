from __future__ import annotations


SERVER_HELP_DESCRIPTION = "Run the local codesys-tools HTTP server."


def build_server_help_epilog() -> str:
    return (
        "Required environment variables:\n"
        "  CODESYS_API_CODESYS_PATH         Path to CODESYS.exe\n"
        "  CODESYS_API_CODESYS_PROFILE      Profile name\n"
        "  CODESYS_API_CODESYS_PROFILE_PATH Path to the .profile.xml file\n"
        "  CODESYS_API_CODESYS_NO_UI        Set to 1 to start CODESYS without a UI window\n\n"
        "Authentication:\n"
        "  All HTTP requests require:\n"
        "    Authorization: ApiKey <key>\n"
        "  The default key \"admin\" is created automatically on first run at:\n"
        "    %APPDATA%\\codesys-api\\api_keys.json\n\n"
        "Endpoints:\n"
        "  session/start, session/status, project/create, project/open, project/save,\n"
        "  project/close, project/compile, pou/create, pou/code, pou/list\n\n"
        "Notes:\n"
        "  HTTP is the primary workflow for persistent multi-step operations\n"
        "  Transport: named_pipe only\n"
        "  project/compile works in both UI and noUI mode\n"
        "  POU declarations sent via pou/code must omit the FUNCTION_BLOCK/PROGRAM header line"
    )
