# Issue #002: POU Object Model Synchronization & Feature Defects

## 1. 问题描述 (Problem Description)
在执行高层级自动化流程（如 G2 编译验证）时，发现 REST API 在处理复杂 POU 结构（带接口实现、方法、属性的 FB）时存在多个关键缺陷：

- **现象 A**: 通过 `pou/create` 创建的 FunctionBlock 无法声明接口（`IMPLEMENTS` 丢失）。
- **现象 B**: 尝试通过 `script/execute` 为 FB 添加 Method/Property 时报错：`"Object 'Method' is not accepted by parent object"`。
- **现象 C**: 在连续 API 调用中，偶尔出现 `❌ List POUs: FAILED - The project handle 0 is invalid`，表明项目句柄丢失。
- **现象 D**: `pou/code` 写入后，FB 内部的方法和属性虽然在代码文本中可见，但在 CODESYS 的项目树（Object Tree）中未作为子对象生成，导致“空壳 FB”。

## 2. 根因分析 (Root Cause Analysis)

### 2.1 接口实现缺失 (`IMPLEMENTS`)
在 `src/codesys_api/ironpython_script_engine.py` 的 `_generate_pou_create_script` 逻辑中，调用 `create_pou` 时仅传递了 `name`, `type`, `language` 参数，未包含 `implements` 逻辑，且未在后续调用中更新 POU 的 Declaration。

### 2.2 对象模型错位 (Object Model Mismatch)
目前的 `pou/code` 逻辑将传入的 ST 代码硬性分割为 `declaration` 和 `implementation`：
- `implementation` 被映射到了 CODESYS 的 `textual_implementation`。
- **冲突点**: 在 CODESYS 中，`textual_implementation` 仅指 POU 的主主体（Body）。`METHOD` 定义属于 POU 的子对象，不应存在于 Body 文本中。将包含 `METHOD` 的完整代码塞进 Body 会导致解析失败。

### 2.3 句柄同步失效 (Handle Synchronization)
在 `PERSISTENT_SESSION.py` 与 `ironpython_script_engine.py` 生成的脚本之间，`session.active_project` 的状态传递可能存在不一致：
- 当脚本执行环境重置或发生异常时，`session.active_project` 可能被置空。
- `POU_LIST` 等操作严重依赖此句柄，句柄失效导致 `Handle 0` 错误。

## 3. 修复计划 (Proposed Fixes)

### 3.1 增强 `pou/create` (修复 A)
- **改动**: 修改 `pou/create` 端点和后端脚本，支持可选的 `implements` 参数（字符串列表）。
- **逻辑**: 在创建 POU 后，立即调用 `pou.set_declaration()` 更新其声明部分以包含 `IMPLEMENTS` 关键字。

### 3.2 优化代码解析逻辑 (修复 B & D)
- **方案**: 废弃在 Python 端手动分割代码的策略。
- **实现**: 如果 `pou/code` 收到包含 `METHOD` 或 `PROPERTY` 关键字的完整代码块，后端脚本应使用更高级的解析器，或者将完整块写入 POU，让 CODESYS 自动重建对象树分支。

### 3.3 句柄保护机制 (修复 C)
- **改动**: 在 `PERSISTENT_SESSION.py` 中增加句柄恢复逻辑。
- **逻辑**: 如果 `session.active_project` 为空，尝试从 `scriptengine.projects.primary` 或 `scriptengine.projects.open_projects` 中自动找回当前活动的项目。

---
**Issue ID**: #002  
**Status**: Open (Analyzed)  
**Priority**: Critical  
**Assigned**: API Implementation Team
