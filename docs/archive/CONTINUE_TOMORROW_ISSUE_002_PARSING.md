# CONTINUE TOMORROW: Issue #002 Parsing Strategy Pivot

## 1. 进展回顾 (Date: 2026-04-12)
今天我们对 `Issue #002: POU Object Model Synchronization & Feature Defects` 进行了深入的修复尝试和 UI 模式下的端到端验证。

我们在 `ironpython_script_engine.py` 中应用了以下修复：
1.  在 `pou/create` 阶段，通过直接操作 `textual_declaration.replace()` 写入 `IMPLEMENTS` 语句。
2.  在 `pou/code` 阶段，尝试提取 `METHOD` 名称，并在向主 POU 写入代码前调用 `create_method()`。
3.  在 `PERSISTENT_SESSION.py` 中加入了 `active_project` 的自愈恢复逻辑。

## 2. 关键发现 (基于 UI 截图的人工验证)
通过在启动了 UI 的 CODESYS 环境中运行测试脚本并查看最终状态截图，我们推翻了部分先前的假设，发现了真实的运行机制：

- **✅ IMPLEMENTS 成功写入**: 截图显示 FB 声明区成功包含了 `IMPLEMENTS I_TestAction, I_TestStatus`。这证明使用 `textual_declaration.replace()` 操作声明头部是正确且生效的。
- **❌ "空壳解析" 的真相**: 截图显示，包含 `METHOD RunTest : BOOL ... END_METHOD` 的**完整大段代码被直接塞进了 FB 的主体实现区域（Body）**。
  - 在 CODESYS 中，FB 的 Body 只能包含该 FB 自身的执行逻辑。
  - `METHOD` 定义不能直接以文本形式存在于 Body 中，这会导致非法的 ST 结构。
  - CODESYS 的脚本引擎**不会**自动为你从 Body 文本中解析出子节点并在项目树中创建它们。这就是为什么我们看到的是“空壳 FB”（有文本，但项目树中没有 Method 节点）。

## 3. 下一步行动计划 (Action Plan for Next Session)
我们必须放弃“将包含 METHOD 的完整大段代码整体塞入 FB 并期望它自动解析”的策略。

接下来的核心任务是：**实现一个真正的 ST 代码结构解析器。**

当 `pou/code` 端点接收到包含 `METHOD` 或 `PROPERTY` 的完整 ST 代码时，系统必须在 Python 端或 IronPython 脚本中执行以下严格拆解流程：

1.  **文本切割 (Parsing)**:
    - 提取 FB 自身的 Declaration 块（从 `FUNCTION_BLOCK` 到第一个 `END_VAR`）。
    - 提取 FB 自身的 Body 块（剥离所有 `METHOD...END_METHOD` 等子块后的剩余代码）。
    - 将每个 `METHOD` 块完整地切分出来，并进一步拆解出 Method 自身的 Declaration 和 Body。
2.  **分步注入 (Injection)**:
    - 首先，更新主 FB 的 `textual_declaration` 和 `textual_implementation`（此时只包含 FB 自己的逻辑）。
    - 然后，遍历解析出的每一个 Method，显式调用 CODESYS API：`m_obj = fb.create_method(m_name, language)`。
    - 最后，针对每一个新创建的子对象 `m_obj`，调用其自身的 `m_obj.textual_declaration.replace()` 和 `m_obj.textual_implementation.replace()` 来分别注入该 Method 的声明和逻辑。

**TDD 建议**：
在明天开始编码前，首先在 Python 端（例如 `tests/unit/` 下）编写单元测试，利用正则表达式或状态机实现对复杂 ST 文本的安全拆解，确保拆分逻辑 100% 正确后，再集成到 `ironpython_script_engine.py` 中。
