"""
CODESYS Persistent Session Script

This script runs as a persistent session inside CODESYS.
It handles commands from the REST API server and executes
operations within the CODESYS environment.

Usage:
    This script is meant to be launched by CODESYS.exe with:
    CODESYS.exe --runscript="PERSISTENT_SESSION.py"

Note:
    This script is written for Python 2.7 compatibility since
    CODESYS uses IronPython 2.7.
"""

import scriptengine
import os
import sys
import time
import json
import traceback
import warnings

NAMED_PIPE_SUPPORT = False
NAMED_PIPE_IMPORT_ERROR = None
try:
    import clr
    try:
        clr.AddReference("System")
    except Exception:
        pass
    try:
        clr.AddReference("System.Core")
    except Exception:
        pass
    from System import Array, Byte
    from System.IO.Pipes import NamedPipeServerStream, PipeDirection, PipeTransmissionMode, PipeOptions
    from System.Text import Encoding
    NAMED_PIPE_SUPPORT = True
except Exception, named_pipe_import_e:
    NAMED_PIPE_IMPORT_ERROR = str(named_pipe_import_e)

# Silence deprecation warnings for sys.exc_clear() in IronPython 2.7
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Check Python version - CODESYS uses IronPython 2.7
PYTHON_VERSION = sys.version_info[0]
IRONPYTHON = 'Iron' in sys.version

# Constants
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSPORT_NAME = os.environ.get("CODESYS_API_TRANSPORT", "named_pipe").strip().lower()
PIPE_NAME = os.environ.get("CODESYS_API_PIPE_NAME", "codesys_api_session")

class CodesysPersistentSession(object):
    """Maintains a persistent CODESYS session."""
    
    def __init__(self):
        self.system = None
        self.active_project = None
        self.running = True
        self.init_success = False
        
    def initialize(self):
        """Initialize the CODESYS environment."""
        try:
            # Log initialization with more details
            self.log("Initializing CODESYS session - started")
            self.log("Python version: " + sys.version)
            self.log("IronPython: " + str(IRONPYTHON))
            self.log("Script directory: " + SCRIPT_DIR)
            self.log("Transport: " + TRANSPORT_NAME)
            self.log("Pipe name: " + PIPE_NAME)
            if not NAMED_PIPE_SUPPORT:
                self.log("Named pipe import status: " + str(NAMED_PIPE_IMPORT_ERROR))
            
            if TRANSPORT_NAME != "named_pipe":
                self.log("Unsupported transport requested in persistent session: " + str(TRANSPORT_NAME))
                self.init_success = False
                return False

            # Test if scriptengine module is available
            if 'scriptengine' not in sys.modules:
                self.log("WARNING: scriptengine module not properly imported")
                self.log("Available modules: " + str(sys.modules.keys()))
            else:
                self.log("ScriptEngine module loaded successfully")
                if hasattr(scriptengine, 'version'):
                    self.log("ScriptEngine version: " + str(scriptengine.version))
            
            # Try loading scriptengine directly to see if it's a module import issue
            try:
                import_result = __import__('scriptengine')
                self.log("Direct import result: " + str(import_result))
                if hasattr(import_result, 'ScriptSystem'):
                    self.log("ScriptSystem class exists in direct import")
                else:
                    self.log("ScriptSystem class NOT found in direct import")
            except:
                error_type, error_value, error_traceback = sys.exc_info()
                self.log("Error directly importing scriptengine: " + str(error_value))
                
            # Initialize the system with retries
            self.system = None
            max_attempts = 3
            
            for attempt in range(max_attempts):
                try:
                    self.log("Getting global scriptengine.system instance (attempt %d of %d)..." % (attempt+1, max_attempts))
                    # Use the global system instance provided by scriptengine
                    self.system = scriptengine.system
                    self.log("Global system instance accessed successfully")
                    
                    # Test system properties
                    if hasattr(self.system, 'version'):
                        self.log("CODESYS version: " + str(self.system.version))
                    elif hasattr(self.system, 'get_version'):
                        self.log("CODESYS version (via method): " + str(self.system.get_version()))
                    else:
                        self.log("System instance accessed but version information not available")
                        
                    # Basic test of system functionality - check if scriptengine.projects is available 
                    if 'projects' in dir(scriptengine):
                        project_count = len(scriptengine.projects) if hasattr(scriptengine.projects, '__len__') else "unknown"
                        self.log("Projects available via global scriptengine.projects: " + str(project_count))
                        # Success - no need for more attempts
                        break
                    else:
                        self.log("Global scriptengine.projects not available, which is unusual")
                        # Try again
                        self.system = None
                        
                except AttributeError, ae:
                    self.log("AttributeError in system initialization (attempt %d): %s" % (attempt+1, str(ae)))
                    self.log("This usually means scriptengine module is not fully loaded or initialized")
                    # Continue with retry
                    self.system = None
                except Exception, e:
                    self.log("Error creating ScriptSystem (attempt %d): %s" % (attempt+1, str(e)))
                    self.log(traceback.format_exc())
                    # Continue with retry
                    self.system = None
                    
                # Wait briefly before retry
                if attempt < max_attempts - 1:
                    self.log("Waiting before retry...")
                    time.sleep(1)
            
            self.init_success = True
            if not NAMED_PIPE_SUPPORT:
                self.log("Named pipe transport requested but .NET named pipe support is unavailable: " + str(NAMED_PIPE_IMPORT_ERROR))
                self.init_success = False
                return False
            if self.system is not None:
                self.log("Initialization successful with working system")
            else:
                self.log("Initialization completed with visible CODESYS but non-functional system")
            return True
        except Exception, e:
            self.log("Initialization failed: %s" % str(e))
            self.log(traceback.format_exc())
            return False
            
    def run(self):
        """Run the persistent session."""
        if not self.init_success:
            self.log("Cannot run - initialization failed")
            return False

        try:
            self.log("Entering named pipe request loop on primary thread")
            self.process_named_pipe_requests()
            self.log("Exiting main loop")
            return True
        except Exception, e:
            self.log("Error in main loop: %s" % str(e))
            self.log(traceback.format_exc())
            return False
        finally:
            # Cleanup
            self.cleanup()
            
    def process_named_pipe_requests(self):
        """Process script execution requests over a named pipe."""
        server = None
        request_id = "unknown"
        try:
            server = NamedPipeServerStream(
                PIPE_NAME,
                PipeDirection.InOut,
                1,
                PipeTransmissionMode.Byte,
                PipeOptions.None
            )
            while self.running:
                try:
                    self.log("Waiting for named pipe client on: " + PIPE_NAME)
                    server.WaitForConnection()
                    self.log("Named pipe client connected on: " + PIPE_NAME)
                    request = self.normalize_named_pipe_request(self.read_named_pipe_request(server))
                    request_id = request.get("request_id", "unknown")
                    self.log("Processing named pipe request: " + str(request_id))
                    script_code = request["script"]
                    result = self.execute_script_content(script_code, "named_pipe:" + str(request_id))
                    result = self.normalize_named_pipe_result(result, request_id)
                    self.write_named_pipe_result(server, result)
                    self.log("Named pipe request completed: " + str(request_id))
                except Exception, e:
                    self.log("Error processing named pipe request: " + str(e))
                    self.log(traceback.format_exc())
                    try:
                        if server is not None and server.IsConnected:
                            self.write_named_pipe_result(server, self.build_named_pipe_failure_response(request_id, str(e)))
                    except Exception, write_e:
                        self.log("Error writing named pipe failure response: " + str(write_e))
                finally:
                    request_id = "unknown"
                    try:
                        if server is not None and server.IsConnected:
                            server.Disconnect()
                            self.log("Named pipe client disconnected from: " + PIPE_NAME)
                    except Exception, disconnect_e:
                        self.log("Error disconnecting named pipe client: " + str(disconnect_e))
        except Exception, outer_e:
            self.log("Fatal named pipe listener error: " + str(outer_e))
            self.log(traceback.format_exc())
        finally:
            try:
                if server is not None:
                    if server.IsConnected:
                        server.Disconnect()
                    server.Close()
            except Exception:
                pass

    def read_named_pipe_request(self, server):
        """Read a single named pipe request."""
        header = self.read_exact_bytes(server, 4)
        message_size = (
            ord(header[0]) |
            (ord(header[1]) << 8) |
            (ord(header[2]) << 16) |
            (ord(header[3]) << 24)
        )
        payload = self.read_exact_bytes(server, message_size)
        request = json.loads(payload)
        if not isinstance(request, dict):
            raise ValueError("Named pipe request payload must be a JSON object")
        return request

    def normalize_named_pipe_request(self, request):
        """Validate and normalize a named-pipe request envelope."""
        required_fields = ("request_id", "script", "timeout_hint", "created_at")
        for field_name in required_fields:
            if field_name not in request:
                raise ValueError("Named pipe request missing required field: " + str(field_name))
        for field_name in ("request_id", "script"):
            field_value = request.get(field_name)
            if not isinstance(field_value, basestring) or not field_value.strip():
                raise ValueError("Named pipe request field must not be empty: " + str(field_name))
        timeout_hint = request.get("timeout_hint")
        created_at = request.get("created_at")
        if not isinstance(timeout_hint, (int, long, float)):
            raise ValueError("Named pipe request field must be numeric: timeout_hint")
        if not isinstance(created_at, (int, long, float)):
            raise ValueError("Named pipe request field must be numeric: created_at")
        return {
            "request_id": request["request_id"],
            "script": request["script"],
            "timeout_hint": timeout_hint,
            "created_at": created_at,
        }

    def build_named_pipe_failure_response(self, request_id, error):
        """Build a normalized named-pipe failure response."""
        return {
            "success": False,
            "error": error,
            "request_id": request_id,
        }

    def normalize_named_pipe_result(self, result, request_id):
        """Normalize a named-pipe response before writing it back."""
        if isinstance(result, dict):
            normalized = dict(result)
        else:
            normalized = {
                "success": True,
                "result": result,
            }
        normalized["request_id"] = request_id
        if "success" not in normalized:
            normalized["success"] = "error" not in normalized
        if not normalized.get("success") and "error" not in normalized:
            normalized["error"] = "Named pipe request failed without an explicit error"
        return normalized

    def write_named_pipe_result(self, server, result):
        """Write a named pipe response."""
        body = json.dumps(result)
        body_bytes = Encoding.UTF8.GetBytes(body)
        size = body_bytes.Length
        header = Array[Byte]([
            size & 0xFF,
            (size >> 8) & 0xFF,
            (size >> 16) & 0xFF,
            (size >> 24) & 0xFF,
        ])
        server.Write(header, 0, 4)
        server.Write(body_bytes, 0, size)
        server.Flush()

    def read_exact_bytes(self, stream, size):
        """Read an exact number of bytes from a .NET stream."""
        buffer = Array.CreateInstance(Byte, size)
        offset = 0
        while offset < size:
            count = stream.Read(buffer, offset, size - offset)
            if count == 0:
                raise IOError("Named pipe stream closed before enough data was read")
            offset += count
        return "".join(chr(int(item)) for item in buffer)
            
    def execute_script(self, script_path):
        """Execute a Python script in the CODESYS environment."""
        try:
            # Log execution start
            self.log("Executing script: %s" % script_path)
            
            # Create globals dict with access to the session
            globals_dict = {
                "session": self,
                "system": self.system,
                "active_project": self.active_project,
                "json": json,
                "os": os,
                "time": time,
                "scriptengine": scriptengine,
                "traceback": traceback,
                "sys": sys
            }
            
            # Load script
            self.log("Loading script content...")
            try:
                with open(script_path, 'r') as f:
                    script_code = f.read()
                self.log("Script loaded successfully (%d bytes)" % len(script_code))
                
                # Log first few lines of script for debugging
                first_lines = script_code.split('\n')[:5]
                self.log("Script preview: %s" % '\n'.join(first_lines))
                
            except Exception, load_e:
                self.log("Error loading script: %s" % str(load_e))
                self.log(traceback.format_exc())
                return {
                    "success": False,
                    "error": "Error loading script: %s" % str(load_e),
                    "traceback": traceback.format_exc()
                }
            return self.execute_script_content(script_code, script_path)
        except Exception, e:
            self.log("Unhandled error in execute_script: %s" % str(e))
            self.log(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": time.time(),
                "executed_by": "CODESYS PersistentSession"
            }

    def execute_script_content(self, script_code, script_label):
        """Execute already-loaded script code in the CODESYS environment."""
        try:
            globals_dict = {
                "session": self,
                "system": self.system,
                "active_project": self.active_project,
                "json": json,
                "os": os,
                "time": time,
                "scriptengine": scriptengine,
                "traceback": traceback,
                "sys": sys
            }

            self.log("Executing script code from: %s" % script_label)
            local_vars = {}
            try:
                exec(script_code, globals_dict, local_vars)
                self.log("Script execution completed successfully")
            except Exception, exec_e:
                self.log("Error executing script: %s" % str(exec_e))
                self.log(traceback.format_exc())
                return {
                    "success": False,
                    "error": str(exec_e),
                    "traceback": traceback.format_exc(),
                    "execution_failed": True
                }

            self.log("Checking for result variable...")
            if "result" in local_vars:
                self.log("Result variable found")
                result = local_vars["result"]
                if isinstance(result, dict):
                    result["execution_time"] = time.time()
                    result["executed_by"] = "CODESYS PersistentSession"
                return result

            self.log("No result variable found, returning default success")
            return {
                "success": True,
                "message": "Script executed successfully (no result variable)",
                "execution_time": time.time(),
                "executed_by": "CODESYS PersistentSession"
            }
        except Exception, e:
            self.log("Unhandled error in execute_script_content: %s" % str(e))
            self.log(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "execution_time": time.time(),
                "executed_by": "CODESYS PersistentSession"
            }
            
    def periodic_tasks(self):
        """Perform periodic tasks."""
        pass
        
    def cleanup(self):
        """Clean up resources before termination."""
        self.log("Cleaning up session")
        
        # Close active project
        if self.active_project:
            try:
                self.log("Closing project: %s" % self.active_project.path)
                
                # Save project if dirty
                if self.active_project.dirty:
                    self.active_project.save()
                    
                # Close project
                self.active_project = None
            except Exception, e:
                self.log("Error closing project: %s" % str(e))
                
        self.log("Cleanup complete")
            
    def log(self, message):
        """Log a message."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_message = "[%s] %s\n" % (timestamp, message)
        sys.stdout.write(log_message)
        sys.stdout.flush()
            
# Main entry point
if __name__ == "__main__":
    # Create and run session
    session = CodesysPersistentSession()
    
    if session.initialize():
        session.run()
    
    # Exit with appropriate code
    sys.exit(0 if session.init_success else 1)
