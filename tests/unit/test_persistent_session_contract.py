from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PERSISTENT_SESSION = REPO_ROOT / "PERSISTENT_SESSION.py"


def read_source() -> str:
    return PERSISTENT_SESSION.read_text(encoding="utf-8")


def test_persistent_session_defines_named_pipe_request_normalization_helpers() -> None:
    source = read_source()

    assert "def normalize_named_pipe_request(self, request):" in source
    assert "def build_named_pipe_failure_response(self, request_id, error):" in source
    assert "def normalize_named_pipe_result(self, result, request_id):" in source
    assert "def process_requests(self):" not in source
    assert "def process_request(self, request_path):" not in source


def test_persistent_session_named_pipe_flow_uses_normalization_helpers() -> None:
    source = read_source()

    assert "request = self.normalize_named_pipe_request(self.read_named_pipe_request(server))" in source
    assert "result = self.normalize_named_pipe_result(result, request_id)" in source
    assert "self.write_named_pipe_result(server, self.build_named_pipe_failure_response(request_id, str(e)))" in source
    assert 'self.request_thread = threading.Thread(target=self.process_named_pipe_requests)' in source
    assert "target=self.process_requests" not in source


def test_persistent_session_named_pipe_request_validates_minimum_fields() -> None:
    source = read_source()

    assert '"request_id", "script", "timeout_hint", "created_at"' in source
    assert "Named pipe request missing required field" in source
    assert "Named pipe request field must not be empty" in source


def test_persistent_session_named_pipe_result_enforces_standard_fields() -> None:
    source = read_source()

    assert '"request_id": request_id' in source
    assert '"success": False' in source
    assert '"error": error' in source


def test_persistent_session_no_longer_defines_file_request_paths() -> None:
    source = read_source()

    assert "REQUEST_DIR =" not in source
    assert "RESULT_DIR =" not in source
    assert "STATUS_FILE =" not in source
    assert "TERMINATION_SIGNAL_FILE =" not in source
    assert "LOG_FILE =" not in source
    assert "Unsupported transport requested in persistent session" in source
    assert "def update_status(self, status):" not in source
    assert "os.path.exists(TERMINATION_SIGNAL_FILE)" not in source


def test_persistent_session_logs_to_stdout_instead_of_file() -> None:
    source = read_source()

    assert "sys.stdout.write(log_message)" in source
    assert "sys.stdout.flush()" in source
    assert "with open(LOG_FILE, 'a')" not in source
