# CODESYS API Debugging Guide

This guide provides step-by-step instructions for troubleshooting connection issues with the CODESYS API HTTP server.

## Quick Start Debugging

1. **Verify CODESYS Path**
   ```
   python debug_codesys_path.py
   ```
   This confirms that the CODESYS executable can be found at the configured path.

2. **Test HTTP Server Only (No CODESYS)**
   ```
   scripts\dev\run_test_server.bat
   ```
   This starts a simplified HTTP server that responds to API requests without connecting to CODESYS.
   Test with: `python scripts\manual\example_client.py` in another window.

3. **Run Full Server**
   ```
   scripts\dev\run_server.bat
   ```
   This starts the complete HTTP server that connects to CODESYS.
   Test with: `python scripts\manual\example_client.py` in another window.

4. **Run Real CODESYS E2E From A Normal User Terminal**
   ```
   python scripts\manual\run_real_codesys_e2e.py
   ```
   Use this for the real HTTP main flow. The runner loads `.env.real-codesys.local`, refuses to run from the Codex sandbox identity, and now defaults real E2E to UI mode instead of `--noUI`.

5. **Probe Python Launch Shape When Profile Auto-Selection Regresses**
   ```
   python scripts\manual\profile_launch_probe.py --mode all
   ```
   Use this when the same manual CODESYS command works but Python-launched CODESYS starts prompting for a profile.

## Detailed Debugging Steps

If you're experiencing connection issues, follow these steps:

### 1. Check CODESYS Installation

Verify that CODESYS is correctly installed and that the path in `HTTP_SERVER.py` matches your installation:

```python
CODESYS_PATH = r"C:\Program Files\CODESYS 3.5.21.0\CODESYS\Common\CODESYS.exe"
```

You can modify this path if your installation is different.

### 2. Check Permissions

Ensure that:
- The script has permission to execute CODESYS
- The temporary directories can be created and written to
- No firewalls are blocking HTTP connections

### 3. Test HTTP Functionality

Run the test server to isolate HTTP issues from CODESYS issues:
```
scripts\dev\run_test_server.bat
```

In another command prompt, run:
```
python scripts\manual\example_client.py
```

If this works, the issue is with CODESYS integration, not HTTP functionality.

### 4. Check Logs

Enable detailed logging in `HTTP_SERVER.py`:
```python
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    # Query /api/v1/system/logs for runtime logs
)
```

Then check the log file after running the server.

### 5. Common Issues and Solutions

#### "Connection aborted" / "RemoteDisconnected" Errors

**Cause**: The server is terminating connections unexpectedly.
**Solutions**:
- Increase timeout values in `HTTP_SERVER.py`
- Check if CODESYS is running correctly
- Verify script execution permissions

#### CODESYS Not Starting

**Cause**: Unable to start CODESYS process.
**Solutions**:
- Check the CODESYS path
- Run CODESYS manually to verify it works
- Check for permissions issues
- If CODESYS starts manually in your own terminal but fails when launched by Codex, compare the Windows identity. Sandbox-launched CODESYS can fail before script startup with `CODESYS.APInstaller.CLI.Program` / `AP Installer` Event Log access errors even when the same command works for the logged-in user.
- If the manual `CODESYS.exe --profile="..." --runscript="..."` command works but Python startup prompts for a profile, compare Python launch modes with `profile_launch_probe.py`. The current product default should follow the `shell_string` startup shape.

#### Real E2E Compile Fails After Working Setup Steps

**Cause**: The compile may succeed, but the noUI compile fallback can still fail while restoring the original runtime.
**What happens**:
- noUI runtime is stopped
- CODESYS is restarted in UI mode for compile
- compile succeeds
- the service switches back to noUI mode and reopens the project
- CODESYS still holds the project lock, so reopen fails with "currently being used" style errors

**Current workaround**:
- Use `python scripts\manual\run_real_codesys_e2e.py` and keep its default `CODESYS_E2E_NO_UI=0`
- Only force `CODESYS_E2E_NO_UI=1` when you are specifically debugging the noUI compatibility path

#### Script Execution Timeouts

**Cause**: Scripts take too long to execute.
**Solution**: Increase the timeout value:
```python
# In HTTP_SERVER.py
SCRIPT_EXECUTION_TIMEOUT = 120  # seconds
```

## Advanced Debugging

For more detailed debugging:

```
debug.bat
```

This will present a menu with additional debugging options:
1. Check CODESYS path
2. Run HTTP server with debugging
3. Run test server
4. Full system test

## Getting Help

If you continue to experience issues after following these steps, please:
1. Collect all log files
2. Note the exact error messages
3. Document which debugging steps you've tried
4. Create a detailed issue in the GitHub repository
