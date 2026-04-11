# Release Notes

## Unreleased

### 0.5.0 — planned

**视觉营销**

- VHS 录制核心操作流程 GIF（`session start` → `pou create` → `project compile`），嵌入 README 顶部 Demo 区域。

---

## 0.4.0 — unreleased

### Summary

DX 增强版本（代号 Visibility & Readiness）。核心目标：降低新用户上手门槛，提升工具在 AI Agent 环境中的识别率。无核心功能变更。

### Changes

**新功能**

- 新增 `codesys-tools doctor` 命令：一键诊断本地环境，涵盖 CODESYS 路径、Profile、pywin32 依赖、命名管道权限、HTTP 服务状态五项检查。每个 `FAIL` 项附带具体修复建议，exit code 语义化（0=全通过，1=有 FAIL）。支持 `--json` 机器可读输出。

**文档**

- 新增根目录 `AGENT.md`：面向 LLM 的工具操作手册，包含 CLI 层级结构、REST 端点映射、错误处理策略及 AI 提示词速查表。
- 新增 `examples/` 目录，包含 3 个可直接执行的 AI 自动化示例脚本：
  - `ai_robust_startup.py` — 诊断先行的健壮启动流程
  - `ai_create_multiple_pous.py` — 批量创建 POU
  - `ai_compile_and_report.py` — 编译结果提取与 CI/CD 失败拦截

### Verification

**Unit and static gate**

- [ ] `python scripts\run_baseline.py` passes

**Packaging gate**

- [ ] `python scripts\build_release.py` succeeds
- [ ] wheel and sdist produced
- [ ] clean wheel-install smoke passes
- [ ] `codesys-tools doctor` entrypoint verified

**PyPI**

- [ ] Published: —
- [ ] Git tag: `v0.4.0`

---

## 0.3.0 — 2026-03-30

### Summary

Workflow reliability hardening from real-CODESYS validation and external user feedback.
All five layers of the Real CODESYS Contract Ladder v1 are GREEN.

### Changes

**Bug fixes**

- Fix HTTP server lifecycle stall: override `log_message()` in `CodesysApiHandler` to
  redirect `BaseHTTPRequestHandler` access logs from `sys.stderr` to a file logger.
  Root cause: E2E tests start the server with `stderr=PIPE`; the anonymous pipe buffer
  (~4 KB) fills after ~7 lifecycles, blocking `send_response()` permanently.
- Fix CODESYS orphan processes on stop: move `taskkill /PID /T /F` before
  `process.terminate()` so the cmd.exe child tree is killed atomically, preventing
  residual CODESYS windows from surviving session stop.
- Add `timeout=10` to the PowerShell `subprocess.run` call in `list_codesys_process_ids()`
  to prevent indefinite blocking when WMI enumeration is slow.
- Remove `application.generate_code()` call after compile — unproven primitive that causes
  a post-compile hang in UI mode by queuing background work in CODESYS's UI layer.
- Remove noUI compile fallback — `build()` works directly in noUI mode; the fallback added
  complexity and caused project-lock errors when switching back from UI mode.

**Architecture**

- Add `proven_primitives.py`: single source of truth for CODESYS scriptengine calls
  validated by real-CODESYS probes. `ironpython_script_engine.py` composes from this module.
- Rebuild `project/create` and session primitives on `scriptengine.projects.create(path, True)`
  instead of `projects.open(Standard.project)` (proven broken in this environment).
- Named pipe transport (`named_pipe_transport.py`) and persistent session
  (`PERSISTENT_SESSION.py`) for reliable multi-step workflows across session boundaries.
- CLI internal logs redirected to `%APPDATA%\codesys-api\logs\codesys_api_cli.log`;
  no longer propagate to stderr, preserving the `--json` contract.

**Documentation**

- `docs/CODESYS_BOUNDARY_CONTRACT.md` — contract between host code and CODESYS scriptengine
- `docs/REAL_CODESYS_LESSONS.md` — lessons from the real-CODESYS investigation
- `docs/BUG_HTTP_LIFECYCLE_STALL.md` — resolved incident report with root-cause analysis
- `docs/DEBUGGING_METHODOLOGY.md` — general debugging methodology extracted from this case

### Verification

**Unit and static gate (pre-release, 2026-03-30)**

- Baseline: `265 passed, mypy clean (82 source files)`
- Branch: `development`, HEAD `0bfe886`

**Real CODESYS E2E (Windows, real CODESYS 3.5.21.0)**

- `http-pipe-stress-lifecycles`: `1 passed` in 381.86s
- `http-all` (8 tests): `8 passed` in 352.37s
- `cli-all` (2 tests): `2 passed` in 95.44s

**Packaging gate** _(to be completed before publish)_

- [ ] `python scripts\build_release.py` succeeds
- [ ] wheel and sdist produced
- [ ] clean wheel-install smoke passes
- [ ] `codesys-tools` entrypoint verified
- [ ] `codesys-tools-server` entrypoint verified
- [ ] `PERSISTENT_SESSION.py` packaged
- [ ] `ScriptLib/` packaged

**TestPyPI** _(to be completed before publish)_

- [ ] `Publish Package (target=testpypi)` passes
- [ ] `Verify Published Package (target=testpypi, version=0.3.0)` passes

**PyPI**

- [ ] Published: —
- [ ] Verified: —
- [ ] Git tag: `v0.3.0`

---

## 0.2.1

- Commit: `a3719c8`
- Baseline gate: `170 passed, 8 skipped`
- Static gate: `mypy` passes with no issues in `60` source files
