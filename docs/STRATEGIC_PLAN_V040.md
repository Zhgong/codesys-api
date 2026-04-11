# v0.4.0 改进计划：DX 增强与 AI 原生化

## 0. 版本定义
*   **版本号**: `v0.4.0`
*   **代号**: “Visibility & Readiness”
*   **核心目标**: 降低新用户上手门槛，提升工具在 AI Agent (Cursor/Claude) 中的识别率。

## 1. 核心任务清单

### A. 产品化增强：`codesys-tools doctor` ✅
借鉴 `opencli` 的自检思想，提供一键式环境诊断。详细定义请参考 [docs/v040_DOCTOR_SPEC.md](v040_DOCTOR_SPEC.md)。
*   **检查项**:
    1.  **CODESYS 检测**: 验证 `CODESYS.exe` 路径是否有效。
    2.  **Profile 验证**: 检查指定的 CODESYS Profile 是否存在。
    3.  **Windows 权限**: 检查当前进程是否具备创建命名管道的权限。
    4.  **服务状态**: 检测 `codesys-tools-server` (HTTP Server) 是否正在运行。
    5.  **依赖项**: 验证 `pywin32` 等关键库是否正确安装。
*   **交付物**: `codesys-tools doctor` 命令及彩色终端输出。

### B. AI 友好化：`AGENT.md` & 结构化文档 ✅
针对 AI Agent (如 Cursor, Claude) 的自动发现机制进行优化。
*   **AGENT.md**: 编写专门针对 LLM 的”工具说明书”，描述 CLI 的分层结构与调试指南。
*   **示例库**: 在 `examples/` 目录下提供 3 个可直接执行的 AI 自动化脚本：
    *   `ai_robust_startup.py` — 诊断先行的健壮启动流程
    *   `ai_create_multiple_pous.py` — 批量创建 POU
    *   `ai_compile_and_report.py` — 编译结果提取与 CI/CD 判定
*   **交付物**: 根目录 `AGENT.md` + `examples/` 目录。

## 2. 改进后的工作流

1.  **新用户**: `pip install codesys-tools` → `codesys-tools doctor`（确认环境 OK）→ 开始使用。
2.  **AI 用户**: 打开项目 → AI 扫描 `AGENT.md` → 自动生成正确的自动化指令。

## 3. 范围说明

视觉化 Demo（VHS 录制 GIF）不纳入本版本，已移至 v0.5.0。

## 4. 技术路线图（已完成）

1.  **Phase 1** ✅: 实现 `codesys-tools doctor` 子命令（`src/codesys_api/cli_entry.py`）。
2.  **Phase 2** ✅: 编写 `AGENT.md` 与 `examples/` 示例库。
