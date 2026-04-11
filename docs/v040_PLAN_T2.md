# Task Description: Phase 2 - AI Friendliness & Structured Docs

## 1. 目标 (Goal)
执行 `STRATEGIC_PLAN_V040.md` 的 Phase 2 计划。核心目标是优化项目，使其对 AI Agent（如 Cursor, Claude 等）更加友好，降低 AI 在生成 CODESYS 自动化脚本时的错误率。

## 2. 修改策略：完善 `AGENT.md`

### 2.1 动作 (Action)
在仓库根目录的 `AGENT.md` 文件中增加全新的章节：**Architecture & Execution Pipeline (For AI Context)**。

### 2.2 详细逻辑要求 (Logic Requirements)
请执行者（Executor）在文件中描述以下系统分层架构：
1.  **分层流转 (The Flow)**：明确指出一条指令从触发到执行经历了三个核心层级：
    *   **CLI / REST Layer** (`src/codesys_api/cli_entry.py` / `HTTP_SERVER.py`)：负责参数解析、格式化输出。
    *   **Action Layer** (`src/codesys_api/action_layer.py`)：处理业务逻辑、状态管理、依赖环境验证（如 `doctor` 逻辑）。
    *   **Engine Layer** (`PERSISTENT_SESSION.py` 等)：实际运行在 CODESYS 内部的 IronPython 2.7 脚本。
2.  **IPC 通信机制**：说明 Action Layer 和 Engine Layer 之间通过文件系统（`requests/` 和 `results/` 目录中的 JSON 文件）进行 IPC 通信。
3.  **故障排查指南 (Debugging for AI)**：指导 AI Agent 在遇到执行失败时如何定位问题：
    *   如果是进程无法启动或网络拒绝，查看 `doctor` 或服务器日志。
    *   如果是 HTTP 500，说明是 CODESYS 内部执行脚本时报错。
    *   强调永远不要去手动修改 `requests/` 目录内的文件。

## 3. 修改策略：生成标准示例库 (`examples/`)

### 3.1 动作 (Action)
在根目录下新建 `examples/` 文件夹（如果不存在），并创建三个专门为 AI Agent 学习准备的 Python 自动化脚本。这三个脚本必须是可以被直接执行的示范代码。

### 3.2 `examples/ai_robust_startup.py`
**设计逻辑**：展示“先诊断，后启动”的健壮型工作流。
1.  使用 `subprocess.run` 调用 `codesys-tools --json doctor`。
2.  解析返回的 JSON，提取 `body["success"]`。
3.  如果失败：遍历 `body["checks"]`，提取 `status == "FAIL"` 的项，打印其 `name` 和 `suggestion`，然后以 `exit(1)` 退出。
4.  如果成功：继续使用 `subprocess.run` 调用 `codesys-tools session start`。

### 3.3 `examples/ai_create_multiple_pous.py`
**设计逻辑**：展示如何通过 Python 循环批量生成 CODESYS 对象。
1.  定义一个示例数据结构（例如包含 3 个 POU 名称及其类型和编程语言的字典或列表）。
2.  使用 `subprocess.run` 在一个 `for` 循环中依次调用 `codesys-tools pou create --name ... --type ... --language ...`。
3.  演示如何在每次调用后检查返回码（`returncode == 0`），如果创建失败应抛出异常或打印警告。

### 3.4 `examples/ai_compile_and_report.py`
**设计逻辑**：展示如何提取结构化的编译结果并用于 CI/CD 判定。
1.  使用 `subprocess.run` 调用 `codesys-tools --json project compile --clean-build`。
2.  解析返回的 JSON 结果。
3.  提取并打印 `body["message_counts"]` 中的统计信息（例如 error 数量、warning 数量）。
4.  实现判定逻辑：如果 error 数量大于 0，即使 CLI 成功执行（返回码 0），脚本也必须以 `exit(1)` 退出，以此示范真正的“构建失败”拦截机制。

## 4. TDD 测试标准与验收条件 (Verification Criteria)

1.  **目录与文件检查**：`examples/` 目录下必须存在上述 3 个完整的 `.py` 文件。
2.  **代码静态检查**：所有 3 个脚本必须通过基础的 Python 语法检查（例如可以使用 `python -m py_compile examples/*.py` 验证）。
3.  **无硬编码路径**：示例代码中不得出现诸如 `C:\Users\username\Desktop\...` 这种特定用户的硬编码路径，应当使用相对路径或占位符，重点演示 CLI 调用逻辑。
4.  **文档审查**：`AGENT.md` 中必须包含架构说明章节，且字数/内容足够支撑 AI Agent 理解整体流转机制。
