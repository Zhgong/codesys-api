import subprocess
import os
import json

# Configuration
CODESYS_PATH = r"C:\Program Files\CODESYS 3.5.20.50\CODESYS\Common\CODESYS.exe"
PROFILE = "CODESYS V3.5 SP20 Patch 5"
PROJECT_PATH = r"C:\Users\vboxuser\Desktop\Repos\codesys-api\DirectProbe.project"
RESULT_FILE = r"C:\Users\vboxuser\Desktop\Repos\codesys-api\probe_result.json"

# IronPython Script - Direct write to avoid f-string issues
IRONPYTHON_SCRIPT = r"""
import scriptengine
import json
import os
import time

try:
    if os.path.exists(r"C:\Users\vboxuser\Desktop\Repos\codesys-api\DirectProbe.project"):
        os.remove(r"C:\Users\vboxuser\Desktop\Repos\codesys-api\DirectProbe.project")
    project = scriptengine.projects.create(r"C:\Users\vboxuser\Desktop\Repos\codesys-api\DirectProbe.project", True)
    app = project.active_application
    
    fb = app.create_pou("Direct_FB", scriptengine.PouType.FunctionBlock)
    
    # CRITICAL: Save project to ensure GUIDs are generated
    project.save()
    
    # Try IMPLEMENTS
    decl_status = "unknown"
    try:
        decl = "FUNCTION_BLOCK Direct_FB IMPLEMENTS I_Direct\nVAR\nEND_VAR"
        if hasattr(fb, "textual_declaration"):
            fb.textual_declaration.replace(decl)
            decl_status = "replace_success"
        else:
            decl_status = "no_decl_api"
    except Exception as e:
        decl_status = "decl_error: " + str(e)
        
    # Try Method
    m_status = "unknown"
    try:
        if hasattr(fb, "create_method"):
            fb.create_method("Direct_Method", scriptengine.ImplementationLanguages.st)
            m_status = "create_method_success"
        else:
            m_status = "no_method_api"
    except Exception as e:
        m_status = "method_error: " + str(e)
        
    result = {
        "success": True,
        "decl": decl_status,
        "method": m_status
    }
    project.save()
    project.close()
except Exception as e:
    result = {"success": False, "error": str(e)}

with open(r"C:\Users\vboxuser\Desktop\Repos\codesys-api\probe_result.json", "w") as f:
    f.write(json.dumps(result))
"""

def run_probe():
    script_path = "temp_probe.py"
    with open(script_path, "w") as f:
        f.write(IRONPYTHON_SCRIPT)
    
    cmd = f'"{CODESYS_PATH}" --profile="{PROFILE}" --runscript="{os.path.abspath(script_path)}"'
    print(f"Running: {cmd}")
    try:
        subprocess.run(cmd, shell=True, timeout=120)
        if os.path.exists(RESULT_FILE):
            with open(RESULT_FILE, "r") as f:
                print(f"Result: {f.read()}")
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)

if __name__ == "__main__":
    run_probe()
