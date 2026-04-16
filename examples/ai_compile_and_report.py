import subprocess
import json
import sys

def main():
    print("Compiling project with clean build...")
    
    # Run the compile command with JSON output
    command = ["codesys-tools", "--json", "project", "compile", "--clean-build"]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        
        # Check if we got any output to parse
        if not result.stdout.strip():
            print(f"Error: CLI command did not return any output.")
            if result.stderr:
                print(f"Stderr: {result.stderr}")
            sys.exit(1)
            
        data = json.loads(result.stdout)
        body = data.get("body", {})
        
        # 1. Report results
        print("\nCompile Result Summary:")
        message_counts = body.get("message_counts", {})
        errors = message_counts.get("errors", 0)
        warnings = message_counts.get("warnings", 0)
        print(f"  - Errors:   {errors}")
        print(f"  - Warnings: {warnings}")
        
        # 2. CI/CD Gate Logic
        # Even if the CLI itself ran successfully (returncode 0), 
        # we might want to fail the build if there are compile errors.
        if errors > 0:
            print("\nBUILD FAILED: Compile errors detected.")
            # Important for CI/CD: Exit with non-zero if business logic (compile) failed
            sys.exit(1)
        
        # Check overall success flag
        if not body.get("success", False):
            print(f"\nBUILD FAILED: Operation success flag is false. Error: {data.get('error', 'Unknown error')}")
            sys.exit(1)
            
        print("\nBUILD SUCCESSFUL: Project compiled without errors.")
        
    except json.JSONDecodeError:
        print("Failed to parse JSON response from CLI.")
        print(f"Raw output: {result.stdout}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
