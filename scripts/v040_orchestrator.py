import json
import sys
import os
import subprocess
import re
import argparse
from pathlib import Path

TASKS_FILE = Path("docs/v040_TASK_DETAILS.json")
PROMPTS_DIR = Path("prompts")
DOCS_DIR = Path("docs")

class LocalAgentClient:
    def __init__(self, tool="gemini"):
        self.tool = tool
        if not self._is_tool_installed(self.tool):
            print(f"Error: {self.tool} is not installed or not in PATH.")
            sys.exit(1)

    def _is_tool_installed(self, name: str) -> bool:
        try:
            subprocess.run([name, "--version"], capture_output=True, check=True, shell=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def ask(self, prompt: str) -> str:
        try:
            if self.tool == "gemini":
                cmd = ["gemini", "-m", "gemini-3.1-pro-preview", "--approval-mode", "plan", "-p", ""]
            elif self.tool == "codex":
                cmd = ["codex", "-m", "gpt-5.3-codex", "exec"]
            else:
                return ""

            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                shell=True
            )
            
            if result.returncode != 0:
                print(f"[{self.tool} Error] Exit code: {result.returncode}")
                print(result.stderr)
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
            
        self.gemini = LocalAgentClient(tool="gemini")
        self.codex = LocalAgentClient(tool="codex")

    def load_role(self, name: str) -> str:
        role_file = PROMPTS_DIR / f"{name}_role.txt"
        if role_file.exists():
            return role_file.read_text(encoding="utf-8")
        return ""

    def get_file_content(self, path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8")
        except Exception as e:
            return f"<File not found or unreadable: {path}>"

    def plan(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            print(f"Error: Task {task_id} not found.")
            return

        print(f"\n[{task_id}] --- PLAN ---")
        context_files = task.get("context", [])
        context_text = ""
        for file in context_files:
            context_text += f"\n--- File: {file} ---\n"
            context_text += self.get_file_content(file)
            context_text += "\n--------------------\n"

        role_prompt = self.load_role("plan")
        prompt = f"""{role_prompt}

任务 ID: {task_id}
任务标题: {task['title']}
任务目标: {task['goal']}
验收标准: {', '.join(task['ac'])}

以下是相关的上下文文件内容：
{context_text}
"""
        print(f">> Thinking (Planning with gemini)...")
        plan_result = self.gemini.ask(prompt)
        
        output_file = DOCS_DIR / f"v040_PLAN_{task_id}.md"
        output_file.write_text(plan_result, encoding="utf-8")
        print(f">> Plan saved to {output_file}")
        print("\n--- Strategy Preview ---\n")
        print(plan_result[:500] + "...")

    def execute(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            print(f"Error: Task {task_id} not found.")
            return

        plan_file = DOCS_DIR / f"v040_PLAN_{task_id}.md"
        if not plan_file.exists():
            print(f"Error: Plan file {plan_file} not found. Run 'plan' first.")
            return

        plan_result = plan_file.read_text(encoding="utf-8")
        
        print(f"\n[{task_id}] --- EXECUTE ---")
        context_files = task.get("context", [])
        context_text = ""
        for file in context_files:
            context_text += f"\n--- File: {file} ---\n"
            context_text += self.get_file_content(file)
            context_text += "\n--------------------\n"

        role_prompt = self.load_role("execute")
        prompt = f"""{role_prompt}

策略内容：
{plan_result}

相关原始文件：
{context_text}
"""
        print(f">> Writing code (Executing with codex)...")
        execute_result = self.codex.ask(prompt)
        
        blocks = re.findall(r"```python\s*# filepath: (.*?)\n(.*?)```", execute_result, re.DOTALL)
        if not blocks:
            blocks = re.findall(r"```[a-zA-Z]*\n# filepath: (.*?)\n(.*?)```", execute_result, re.DOTALL)
            
        if not blocks:
            print(">> No valid code blocks found. Output:")
            print(execute_result)
            return

        for filepath, content in blocks:
            filepath = filepath.strip()
            print(f">> Writing to {filepath}...")
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            Path(filepath).write_text(content, encoding="utf-8")
            print(">> Done.")

    def audit(self, task_id: str):
        task = self.tasks.get(task_id)
        if not task:
            print(f"Error: Task {task_id} not found.")
            return

        print(f"\n[{task_id}] --- AUDIT ---")
        role_prompt = self.load_role("audit")
        prompt = f"""{role_prompt}

任务 ID: {task_id}
任务目标: {task['goal']}
验收标准: {', '.join(task['ac'])}
"""
        print(f">> Auditing (Reviewing with gemini)...")
        audit_result = self.gemini.ask(prompt)
        print(audit_result)

def main():
    parser = argparse.ArgumentParser(description="v0.4.0 Phased Orchestrator")
    parser.add_argument("command", choices=["plan", "execute", "audit", "run-all"], help="Command to run")
    parser.add_argument("task_id", nargs="?", help="Task ID (e.g., T1)")
    
    args = parser.parse_args()
    
    orch = V040Orchestrator()
    
    if args.command == "run-all":
        for tid in orch.tasks:
            orch.plan(tid)
            orch.execute(tid)
            orch.audit(tid)
    else:
        if not args.task_id:
            print("Error: task_id is required for plan/execute/audit")
            sys.exit(1)
        if args.command == "plan":
            orch.plan(args.task_id)
        elif args.command == "execute":
            orch.execute(args.task_id)
        elif args.command == "audit":
            orch.audit(args.task_id)

if __name__ == "__main__":
    main()
