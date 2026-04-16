import subprocess
import json
import sys

def run_command(command):
    """Utility to run a shell command and return the JSON output."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False # We handle returncode manually
        )
        if result.returncode != 0 and not result.stdout:
            print(f"Error executing {' '.join(command)}: {result.stderr}")
            return None
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            print(f"Failed to parse JSON from {' '.join(command)}")
            print(f"Raw output: {result.stdout}")
            return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

def main():
    print("Step 1: Running Diagnostics...")
    doctor_result = run_command(["codesys-tools", "--json", "doctor"])
    
    if not doctor_result:
        print("CRITICAL: Failed to run diagnostics.")
        sys.exit(1)
        
    # Check if doctor reported success
    # Every response follows the structure: {"body": {"success": bool, ...}, "error": ...}
    body = doctor_result.get("body", {})
    if not body.get("success", False):
        print("DIAGNOSTICS FAILED:")
        checks = body.get("checks", [])
        for check in checks:
            if check.get("status") == "FAIL":
                name = check.get("name", "Unknown Check")
                suggestion = check.get("suggestion", "No suggestion provided.")
                print(f"  - [{name}]: {suggestion}")
        
        print("\nPlease fix the issues above before starting a session.")
        sys.exit(1)
        
    print("Diagnostics passed. Proceeding to start session...")
    
    # Step 2: Start session
    start_result = run_command(["codesys-tools", "--json", "session", "start"])
    
    if start_result and start_result.get("body", {}).get("success", False):
        print("Session started successfully.")
    else:
        error_msg = start_result.get("error", "Unknown error") if start_result else "Failed to get response"
        print(f"Failed to start session: {error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
