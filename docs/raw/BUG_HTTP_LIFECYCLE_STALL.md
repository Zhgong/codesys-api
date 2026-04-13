# Bug Report: HTTP Lifecycle Stall (Resolved)

## Status

- Resolved
- Date closed: 2026-03-29

## Original Symptom

`test_pipe_stress_repeated_lifecycles` 在同一个 HTTP server 生命周期内执行 8 轮
`session/start -> project/create -> pou/code -> session/stop`，
在第 7 或第 8 轮出现 HTTP 请求超时，表现为客户端等待 `/api/v1/session/status`
响应时 `socket.recv_into` 超时。

## Root Cause

最终根因在 HTTP 层，不在 ActionService 或 ProcessManager：

- `BaseHTTPRequestHandler.send_response()` 会调用 `log_request()`，
  默认路径会写到 `sys.stderr`。
- E2E 场景中 server 进程经常以 `stderr=PIPE` 启动，且不持续消费该管道。
- 请求次数累积后，`stderr` 管道被写满，`send_response()` 阻塞，
  进而看起来像“HTTP server 停住不再响应”。

这解释了“前几轮正常、后几轮卡死”的生命周期特征：是输出背压累积触发，不是业务逻辑死锁。

## Fix Applied

### 1) HTTP 修复（主修复）

在 `CodesysApiHandler` 覆盖 `log_message()`，不再向 `stderr` 写访问日志，
改为写文件 logger，避免 `stderr` 管道背压阻塞请求处理。

- File: `src/codesys_api/http_server.py`
- Key behavior change:
  - before: `BaseHTTPRequestHandler` 默认 `stderr` access log
  - after: access log -> file logger (`codesys_api_server.log`)

同时移除了排障期临时 `[diag]` 日志，恢复常态日志噪音水平。

### 2) 相关稳定性修复（同阶段）

`codesys_process.py` 中保留已验证修复：

- `taskkill /T /F` 前置，优先清理 shell tree，避免 CODESYS 子进程遗留。
- `list_codesys_process_ids()` 增加超时保护，避免外部进程枚举无期限阻塞。

## Validation Evidence

以下为真实环境通过结果（Windows 本机 + real CODESYS）：

```powershell
python scripts\manual\run_real_codesys_e2e.py --target http-pipe-stress-lifecycles
# 1 passed, 1 deselected in 381.86s (0:06:21)
```

```powershell
python scripts\manual\run_real_codesys_e2e.py --target http-all
# 8 passed in 352.37s (0:05:52)
```

另外，跨入口回归（CLI）在后续修复后也通过：

```powershell
python scripts\manual\run_real_codesys_e2e.py --target cli-all
# 2 passed in 95.44s (0:01:35)
```

## Follow-up: CLI `stderr` Contamination (Separate Issue, Also Resolved)

在修复 HTTP stall 后，`cli-all` 曾失败，但这是独立问题：

- 原因：CLI 内部 warning 日志泄漏到 `stderr`，破坏了 `--json` 路径下
  `stderr == ""` 的测试契约。
- 处理：将 CLI 内部日志定向到
  `%APPDATA%\codesys-api\logs\codesys_api_cli.log`，
  并禁止 logger 向 root/`stderr` 传播。

该问题与 HTTP lifecycle stall 根因不同，但现已一并修复并通过回归。

## Final Conclusion

`docs/BUG_HTTP_LIFECYCLE_STALL.md` 对应的原始故障已经闭环：

- HTTP 生命周期卡死已消失。
- 目标验收命令 `http-pipe-stress-lifecycles` 与 `http-all` 均通过。
- 跨入口回归 `cli-all` 也通过。
