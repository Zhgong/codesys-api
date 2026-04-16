# codesys-tools doctor 功能规范与验收标准

## 1. 功能定义
该命令的目标是**“在 3 秒内识别 90% 的常见配置错误”**。它将分为四个层级的检查：

### A. 静态配置检查 (Configuration Audit)
*   **环境变量**: 检查 `CODESYS_API_CODESYS_PATH` 和 `CODESYS_API_CODESYS_PROFILE` 是否已定义。
*   **配置文件**: 如果存在本地配置文件，验证其格式是否正确。

### B. 系统环境检查 (System Environment)
*   **操作系统**: 确认当前操作系统是否为 Windows（该项目目前仅支持 Windows）。
*   **Python 依赖**: 
    *   验证 `pywin32` 是否安装（这是 Named Pipe 传输的基础，最容易被用户忽略）。
    *   验证 `requests` 是否安装。
*   **二进制验证**: 验证 `CODESYS.exe` 路径是否真实存在，且当前用户是否有执行权限。

### C. 运行能力检查 (Runtime Capability)
*   **IPC (命名管道) 测试**: 尝试创建一个临时的命名管道 `\\.\pipe\codesys_api_doctor_test`，验证当前用户是否有足够的 Windows 权限进行进程间通信。
*   **端口占用**: 检查配置的 HTTP 端口（默认 8080）是否被其他应用占用。

### D. 连通性探测 (Connectivity Probe)
*   **服务器存活**: 尝试向 `codesys-tools-server` 发送一个轻量级的 ping/status 请求，确认后台服务是否在线。

---

## 2. 验收标准 (Acceptance Criteria)

只有满足以下所有标准，该功能才算“完成”：

1.  **交互友好性 (UX)**:
    *   使用清晰的标识：通过 `[PASS]`, `[FAIL]`, `[WARN]` 来区分严重程度。
    *   **关键点**：每一个 `[FAIL]` 后面必须紧跟一条 **“建议修复动作”**（例如：“请运行 `pip install pywin32`”）。

2.  **退出码规范**:
    *   如果所有**关键检查**（Critical Checks）通过，退出码必须为 `0`。
    *   如果有任何关键检查失败（导致工具完全无法工作），退出码必须为 `1`。

3.  **无副作用 (Read-only)**:
    *   `doctor` 命令不应修改任何系统配置、环境变量或项目文件。
    *   测试用的临时命名管道必须在检查结束后立即关闭并清理。

4.  **性能表现**:
    *   全套自检流程在本地机器上的执行时间不得超过 **2 秒**。

5.  **错误鲁棒性**:
    *   如果某个检查项发生异常（如权限不足），`doctor` 不应崩溃，应捕获异常并标记该项为 `[FAIL]` 并显示具体原因。
