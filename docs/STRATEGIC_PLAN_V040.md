# v0.4.0 改进计划：DX 增强与 AI 原生化 (OpenCLI 启发)

## 0. 版本定义
*   **版本号**: `v0.4.0`
*   **代号**: "Visibility & Readiness"
*   **核心目标**: 降低新用户上手门槛，提升工具在 AI Agent (Cursor/Claude) 中的识别率，通过视觉化演示增强品牌吸引力。

## 1. 核心任务清单

### A. 产品化增强：`codesys-tools doctor`
借鉴 `opencli` 的自检思想，提供一键式环境诊断。详细定义请参考 [docs/v040_DOCTOR_SPEC.md](v040_DOCTOR_SPEC.md)。
*   **检查项**:
    1.  **CODESYS 检测**: 验证 `CODESYS.exe` 路径是否有效。
    2.  **Profile 验证**: 检查指定的 CODESYS Profile 是否存在。
    3.  **Windows 权限**: 检查当前进程是否具备创建命名管道的权限。
    4.  **服务状态**: 检测 `codesys-tools-server` (HTTP Server) 是否正在运行。
    5.  **依赖项**: 验证 `pywin32` 等关键库是否正确安装。
*   **交付物**: `codesys-tools doctor` 命令及彩色终端输出。

### B. AI 友好化：`AGENT.md` & 结构化文档
针对 AI Agent (如 Cursor) 的自动发现机制进行优化。
*   **AGENT.md**: 编写专门针对 LLM 的“工具说明书”，描述 CLI 的分层结构。
*   **示例库**: 在 `examples/` 目录下增加 3 个 AI 最容易生成的典型脚本（如：一键创建 10 个报警 POU）。
*   **交付物**: 根目录 `AGENT.md`。

### C. 视觉营销：GitHub 动态演示 (Demo Video)
让用户在 15 秒内理解产品价值。
*   **场景设计**: 采用“左侧 CLI 录入 -> 右侧 CODESYS 实时反应”的双窗联动。
*   **关键动作**:
    1. `session start` (CODESYS 窗口弹出)
    2. `pou create` (项目树实时出现新 POU)
    3. `project compile` (终端返回 errors=0)
*   **技术手段**: 使用 **VHS** 录制高清晰度 GIF/MP4。
*   **交付物**: README.md 顶部的动态 Demo 区域。

## 2. 改进后的工作流

1.  **新用户**: `pip install codesys-tools` -> `codesys-tools doctor` (确认环境 OK) -> 观看 GIF (理解玩法)。
2.  **AI 用户**: 打开项目 -> AI 扫描 `AGENT.md` -> 自动帮用户写出正确的自动化指令。

## 3. 技术路线图

1.  **Phase 1**: 修改 `src/codesys_api/cli_entry.py`，注册并实现 `doctor` 子命令。
2.  **Phase 2**: 编写 `AGENT.md`，梳理所有的 CLI 指令和参数边界。
3.  **Phase 3**: 配置 **VHS** 脚本，录制核心流程，更新 README。
