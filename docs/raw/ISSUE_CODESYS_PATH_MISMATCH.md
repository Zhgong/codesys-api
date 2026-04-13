# Issue: Failed to start CODESYS process (Path Mismatch)

## 1. 问题描述 (Problem Description)
用户在通过 REST API 启动 CODESYS 会话时失败：
- **请求**: `POST http://127.0.0.1:8080/api/v1/session/start`
- **响应**: `{"success": false, "error": "Failed to start CODESYS process"}`
- **HTTP 状态码**: 500 Internal Server Error
- **用户观察**:
    - HTTP 服务器运行正常（401/404 响应正常）。
    - 认证不是主要障碍，即使跳过认证也会因为找不到进程而失败。

## 2. 问题分析与排查 (Diagnosis & Investigation)

### 2.1 核心原因：硬编码路径不匹配
经过代码审计与系统扫描发现：
- **默认配置**: 在 `src/codesys_api/server_config.py` 中，默认 CODESYS 路径被硬编码为 `C:\Program Files\CODESYS 3.5.21.0\CODESYS\Common\CODESYS.exe`。
- **环境实际状况**: 用户机器上安装的版本是 `3.5.20.50`，实际路径为 `C:\Program Files\CODESYS 3.5.20.50\CODESYS\Common\CODESYS.exe`。
- **日志确认**: 在 `%APPDATA%\codesys-api\logs\codesys_api_server.log` 中记录了明确的错误：
  `ERROR - CODESYS executable not found at path: C:\Program Files\CODESYS 3.5.21.0\...`

### 2.2 辅助发现：Profile 配置需求
日志显示，CODESYS 启动时需要特定的 Profile 参数：`--profile="CODESYS V3.5 SP20 Patch 5"`。如果缺省，可能导致 CODESYS 弹出 UI 选择框，从而导致自动化流程挂起或超时。

### 2.3 认证逻辑说明
- 系统默认在初次启动时于 `%APPDATA%\codesys-api\api_keys.json` 生成一个 `admin` 密钥。
- 即使认证通过，若路径错误，依然会返回 `500` 错误。

## 3. 修复建议 (Recommendation)

### 3.1 临时解决方案 (推荐)
无需修改代码，使用环境变量覆盖默认路径。在启动服务器前执行以下 PowerShell 命令：

```powershell
$env:CODESYS_API_CODESYS_PATH = "C:\Program Files\CODESYS 3.5.20.50\CODESYS\Common\CODESYS.exe"
$env:CODESYS_API_CODESYS_PROFILE = "CODESYS V3.5 SP20 Patch 5"
python .\HTTP_SERVER.py
```

### 3.2 长期改进方案
1. **自动路径探测**: 改进 `src/codesys_api/server_config.py`，增加对 `C:\Program Files\` 下不同版本 CODESYS 目录的遍历探测，而非仅仅依赖单一硬编码路径。
2. **配置文件外部化**: 鼓励用户通过 `.env` 文件或项目根目录下的 `config.json` 来定义路径，而非修改库代码。
3. **更清晰的启动错误提示**: 在 `CodesysProcessManager` 中，如果路径不存在，除了日志记录外，应在 API 响应中返回更具体的错误（例如 "CODESYS executable not found" 而非通用的 "Failed to start"）。

---
**Status**: Analyzed | **Priority**: High | **Assigned**: Environment Setup
