import json
import sys
import os
import subprocess
import re
from pathlib import Path

TASKS_FILE = Path("docs/v040_TASK_DETAILS.json")

class LocalAgentClient:
    def __init__(self, tool="gemini"):
        self.tool = tool
        # 检查工具是否可用
        if not self._is_tool_installed(self.tool):
            print(f"Error: {self.tool} is not installed or not in PATH.")
            sys.exit(1)

    def _is_tool_installed(self, name: str) -> bool:
        try:
            subprocess.run([name, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def ask(self, prompt: str) -> str:
        """通过 stdin 将 prompt 发送给本地 CLI 工具并获取标准输出"""
        try:
            if self.tool == "gemini":
                # 使用 --approval-mode plan 确保它只做文本生成，不自动改文件
                # 使用 -p 加上 stdin 管道输入，避免参数过长
                cmd = ["gemini", "-m", "gemini-3.1-pro-preview", "--approval-mode", "plan", "-p", ""]
            elif self.tool == "codex":
                # codex 的非交互执行模式
                cmd = ["codex", "-m", "gpt-5.3-codex high", "exec"]
            else:
                return ""

            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8"
            )
            
            if result.returncode != 0:
                print(f"[{self.tool} Error] Exit code: {result.returncode}")
                print(result.stderr)
                # 即使有错，有时 stdout 也会包含部分生成的文本
                return result.stdout + "\n" + result.stderr
            
            return result.stdout
        except Exception as e:
            print(f"[Execution Error] Failed to call {self.tool}: {e}")
            return ""

class V040Orchestrator:
    def __init__(self):
        if not TASKS_FILE.exists():
            print(f"Error: {TASKS_FILE} not found.")
            sys.exit(1)
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            self.tasks = json.load(f)
            
        # 分别初始化两个客户端
        self.gemini = LocalAgentClient(tool="gemini")
        self.codex = LocalAgentClient(tool="codex")

    def get_file_content(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except Exception as e:
            return f"<File not found or unreadable: {path}>"

    def plan(self, task_id: str, task: dict) -> str:
        print(f"\n[{task_id}] --- PLAN ---")
        context_files = task.get("context", [])
        context_text = ""
        for file in context_files:
            context_text += f"\n--- File: {file} ---\n"
            context_text += self.get_file_content(file)
            context_text += "\n--------------------\n"

        prompt = f"""
你是一个高级 Python 开发人员。请分析以下任务。
任务 ID: {task_id}
任务标题: {task['title']}
任务目标: {task['goal']}
验收标准: {', '.join(task['ac'])}

以下是相关的上下文文件内容：
{context_text}

请给出一个清晰的、一步一步的代码修改策略，指出需要修改哪些文件的哪些行，并说明原因。不要直接写出完整的代码，只需给出策略。
"""
        print(f">> Thinking (Planning with gemini)...")
        plan_result = self.gemini.ask(prompt)
        print(plan_result)
        return plan_result

    def execute(self, task_id: str, task: dict, plan_result: str):
        print(f"\n[{task_id}] --- EXECUTE ---")
        context_files = task.get("context", [])
        context_text = ""
        for file in context_files:
            context_text += f"\n--- File: {file} ---\n"
            context_text += self.get_file_content(file)
            context_text += "\n--------------------\n"

        prompt = f"""
根据之前的分析策略，请输出具体的代码变更。你现在处于文本生成模式，请直接输出代码文本。
策略内容：
{plan_result}

相关文件：
{context_text}

请提供完整的、可以直接覆写原文件的最终代码。
格式要求：
对于每一个需要修改的文件，请使用如下严格格式输出：
```python
# filepath: path/to/file.py
<此处为文件的完整代码>
```
只输出代码块，不要省略任何逻辑，确保可以直接保存运行。
"""
        print(f">> Writing code (Executing with codex)...")
        execute_result = self.codex.ask(prompt)
        
        # 解析并写入文件
        blocks = re.findall(r"```python\s*# filepath: (.*?)\n(.*?)```", execute_result, re.DOTALL)
        if not blocks:
            # 兼容可能的普通 markdown 格式
            blocks = re.findall(r"```[a-zA-Z]*\n# filepath: (.*?)\n(.*?)```", execute_result, re.DOTALL)
            
        if not blocks:
            print(">> No valid code blocks found. The agent might have formatted it differently.")
            print(execute_result)
            return

        for filepath, content in blocks:
            filepath = filepath.strip()
            print(f">> Writing to {filepath}...")
            # 确保父目录存在
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(content, encoding="utf-8")
            print(">> Done.")

    def audit(self, task_id: str, task: dict):
        print(f"\n[{task_id}] --- AUDIT ---")
        prompt = f"""
任务已执行完成。请根据以下任务信息和验收标准，给出一个简短的、可以直接复制运行的测试命令清单（Checklist），告诉用户接下来应该如何手动验证代码是否生效。
任务 ID: {task_id}
任务目标: {task['goal']}
验收标准: {', '.join(task['ac'])}
"""
        print(f">> Auditing (Reviewing with gemini)...")
        audit_result = self.gemini.ask(prompt)
        print(audit_result)

        print(f"\n>> 原始验收标准 (AC):")
        for ac in task['ac']:
            print(f"  - [ ] {ac}")
        print(">> Audit phase complete.")

    def run_all(self):
        print("================================")
        print(" Starting v0.4.0 Orchestrator")
        print(" Engines: PLAN/AUDIT=gemini, EXECUTE=codex")
        print("================================")
        for task_id, task in self.tasks.items():
            print(f"\n>>> Starting Task: {task_id} - {task['title']}")
            plan_res = self.plan(task_id, task)
            self.execute(task_id, task, plan_res)
            self.audit(task_id, task)
            
            user_input = input(f"\nTask {task_id} complete. Continue to next task? (y/N): ")
            if user_input.lower() != 'y':
                print("Aborting remaining tasks.")
                break
        print("\nAll tasks completed!")

if __name__ == "__main__":
    try:
        orch = V040Orchestrator()
        orch.run_all()
    except KeyboardInterrupt:
        print("\nAborted by user.")
