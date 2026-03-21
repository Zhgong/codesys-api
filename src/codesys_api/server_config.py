from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .runtime_paths import default_api_key_file, packaged_persistent_script, packaged_script_lib_dir


DEFAULT_SERVER_HOST = "0.0.0.0"
DEFAULT_SERVER_PORT = 8080
DEFAULT_CODESYS_PATH = Path(r"C:\Program Files\CODESYS 3.5.21.0\CODESYS\Common\CODESYS.exe")
DEFAULT_TRANSPORT = "named_pipe"
DEFAULT_PIPE_NAME = "codesys_api_session"
REMOVAL_CANDIDATE_TRANSPORTS = frozenset({"file"})


@dataclass(frozen=True)
class ServerConfig:
    server_host: str
    server_port: int
    codesys_path: Path
    codesys_profile_name: str | None
    codesys_profile_path: Path | None
    codesys_no_ui: bool
    transport_name: str
    pipe_name: str
    script_dir: Path
    persistent_script: Path
    api_key_file: Path
    script_lib_dir: Path

    @property
    def transport_is_legacy(self) -> bool:
        return self.transport_name in REMOVAL_CANDIDATE_TRANSPORTS

    @property
    def transport_is_primary(self) -> bool:
        return self.transport_name == DEFAULT_TRANSPORT

    @property
    def transport_is_supported(self) -> bool:
        return self.transport_is_primary

    @property
    def transport_is_removal_candidate(self) -> bool:
        return self.transport_is_legacy

    @property
    def transport_role(self) -> str:
        if self.transport_is_removal_candidate:
            return "unsupported_removal_candidate"
        if not self.transport_is_supported:
            return "unsupported"
        return "primary"

    @property
    def recommended_transport(self) -> str:
        return DEFAULT_TRANSPORT

    def build_transport_info(self) -> dict[str, Any]:
        return {
            "transport": self.transport_name,
            "transport_role": self.transport_role,
            "transport_legacy": self.transport_is_legacy,
            "transport_removal_candidate": self.transport_is_removal_candidate,
            "recommended_transport": self.recommended_transport,
            "pipe_name": self.pipe_name,
        }


def _profile_name_from_path(profile_path: Path) -> str:
    name = profile_path.name
    suffix = ".profile.xml"
    if name.lower().endswith(suffix):
        return name[: -len(suffix)]
    return profile_path.stem


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _find_profile_candidates(codesys_path: Path) -> list[Path]:
    install_root = codesys_path.parent.parent
    primary_profiles_dir = install_root / "Profiles"
    fallback_profiles_dir = install_root / "AdditionalFolders" / "Default" / "Profiles"

    for profiles_dir in (primary_profiles_dir, fallback_profiles_dir):
        if not profiles_dir.exists():
            continue

        candidates = sorted(
            path for path in profiles_dir.glob("*.profile.xml") if path.is_file()
        )
        if candidates:
            return candidates

    return []


def load_server_config(base_dir: Path, env: Mapping[str, str]) -> ServerConfig:
    server_host = env.get("CODESYS_API_SERVER_HOST", DEFAULT_SERVER_HOST)
    server_port = int(env.get("CODESYS_API_SERVER_PORT", str(DEFAULT_SERVER_PORT)))
    codesys_path = Path(env.get("CODESYS_API_CODESYS_PATH", str(DEFAULT_CODESYS_PATH)))
    profile_path_value = env.get("CODESYS_API_CODESYS_PROFILE_PATH")
    profile_name_value = env.get("CODESYS_API_CODESYS_PROFILE")
    codesys_no_ui = _parse_bool(env.get("CODESYS_API_CODESYS_NO_UI"), False)
    transport_name = env.get("CODESYS_API_TRANSPORT", DEFAULT_TRANSPORT).strip().lower()
    pipe_name = env.get("CODESYS_API_PIPE_NAME", DEFAULT_PIPE_NAME)

    codesys_profile_path = Path(profile_path_value) if profile_path_value else None
    if profile_name_value:
        codesys_profile_name = profile_name_value
    elif codesys_profile_path is not None:
        codesys_profile_name = _profile_name_from_path(codesys_profile_path)
    else:
        candidates = _find_profile_candidates(codesys_path)
        if len(candidates) == 1:
            codesys_profile_path = candidates[0]
            codesys_profile_name = _profile_name_from_path(codesys_profile_path)
        else:
            codesys_profile_name = None

    return ServerConfig(
        server_host=server_host,
        server_port=server_port,
        codesys_path=codesys_path,
        codesys_profile_name=codesys_profile_name,
        codesys_profile_path=codesys_profile_path,
        codesys_no_ui=codesys_no_ui,
        transport_name=transport_name,
        pipe_name=pipe_name,
        script_dir=base_dir,
        persistent_script=packaged_persistent_script(),
        api_key_file=default_api_key_file(env),
        script_lib_dir=packaged_script_lib_dir(),
    )
