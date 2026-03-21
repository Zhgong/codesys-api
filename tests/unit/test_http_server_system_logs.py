from __future__ import annotations

from HTTP_SERVER import build_system_logs


class FakeProcessManager:
    def __init__(self, logs: list[str]) -> None:
        self.logs = logs

    def get_log_lines(self) -> list[str]:
        return list(self.logs)


def test_build_system_logs_returns_current_process_manager_buffer() -> None:
    result = build_system_logs(FakeProcessManager(["line one\n", "line two\n"]))

    assert result == {
        "success": True,
        "logs": ["line one\n", "line two\n"],
    }


def test_build_system_logs_returns_empty_list_when_process_manager_is_missing() -> None:
    result = build_system_logs(None)

    assert result == {
        "success": True,
        "logs": [],
    }
