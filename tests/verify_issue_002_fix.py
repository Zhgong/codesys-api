import requests
import json
import time

# Configuration
URL = "http://localhost:8080/api/v1"
HEADERS = {
    "Authorization": "ApiKey admin",
    "Content-Type": "application/json"
}

def verify_fix():
    print("=== Starting Issue #002 Fix Verification ===")
    
    # 1. Start session (ensure it's active)
    print("\n1. Ensuring session is started...")
    res = requests.post(f"{URL}/session/start", headers=HEADERS)
    print(f"Response: {res.status_code} - {res.text}")
    
    # Wait for session to stabilize
    time.sleep(2)

    # 1.5 Create a new project (Crucial step!)
    print("\n1.5 Creating a new project...")
    project_params = {
        "path": "C:/Users/vboxuser/Desktop/Repos/codesys-api/Verify002.project"
    }
    res = requests.post(f"{URL}/project/create", json=project_params, headers=HEADERS)
    print(f"Response: {res.status_code} - {res.text}")
    
    # Save after create
    requests.post(f"{URL}/project/save", headers=HEADERS)

    # 2. Create a Function Block with 'implements'
    # Note: Even if the interface doesn't exist, the declaration should be updated.
    print("\n2. Creating FB with 'implements' parameter...")
    fb_params = {
        "name": "FB_V002_Test",
        "type": "FunctionBlock",
        "language": "ST",
        "implements": ["I_TestAction", "I_TestStatus"]
    }
    res = requests.post(f"{URL}/pou/create", json=fb_params, headers=HEADERS)
    print(f"Response: {res.status_code} - {res.text}")
    
    # Save after POU create
    requests.post(f"{URL}/project/save", headers=HEADERS)
    
    # 3. Update POU with full ST block including METHOD
    print("\n3. Updating FB with full ST code (including METHOD)...")
    full_code = """FUNCTION_BLOCK FB_V002_Test IMPLEMENTS I_TestAction, I_TestStatus
VAR
    _counter : INT;
END_VAR
METHOD RunTest : BOOL
VAR_INPUT
END_VAR
_counter := _counter + 1;
RunTest := TRUE;
END_METHOD"""
    
    code_params = {
        "path": "FB_V002_Test",
        "code": full_code
    }
    res = requests.post(f"{URL}/pou/code", json=code_params, headers=HEADERS)
    print(f"Response: {res.status_code} - {res.text}")

    # Final Save
    print("\nFinalizing: Saving project...")
    requests.post(f"{URL}/project/save", headers=HEADERS)

    # 4. Verify POU List (Check handle stability)
    print("\n4. Verifying POU list (Handle stability check)...")
    res = requests.get(f"{URL}/pou/list", params={"parentPath": "Application"}, headers=HEADERS)
    print(f"Response: {res.status_code}")
    if res.status_code == 200:
        pous = res.json().get("pous", [])
        found = any(p["name"] == "FB_V002_Test" for p in pous)
        print(f"POU 'FB_V002_Test' found in list: {found}")
    else:
        print(f"FAILED to list POUs: {res.text}")

    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    verify_fix()
