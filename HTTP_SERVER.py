#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
CODESYS API HTTP Server

This script implements a HTTP server for the CODESYS API wrapper.
It provides RESTful endpoints to interact with CODESYS through
a persistent session.

Note: This script requires Python 3.x.
Only the PERSISTENT_SESSION.py script maintains compatibility with
CODESYS IronPython environment.
"""

import sys
import os
import json
import time
import subprocess
import threading
import tempfile
import uuid
import shutil
import logging
import traceback
from pathlib import Path
from typing import Any

from action_layer import ActionRequest, ActionService, ActionType
from api_key_store import ApiKeyManager
from codesys_process import CodesysProcessManager, ProcessManagerConfig
from ironpython_script_engine import IronPythonScriptEngineAdapter
from server_config import load_server_config
from session_transport import build_script_transport
from server_logic import (
    build_default_project_path,
    build_status_payload,
    normalize_project_create_params,
    validate_pou_code_params,
    validate_required_params,
)

# Python 3 compatibility imports
try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import urllib.parse as urlparse
except ImportError:
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
    import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='codesys_api_server.log'
)
logger = logging.getLogger('codesys_api_server')

APP_CONFIG = load_server_config(Path(__file__).resolve().parent, os.environ)

# Constants kept for compatibility with existing script generation and handlers.
SERVER_HOST = APP_CONFIG.server_host
SERVER_PORT = APP_CONFIG.server_port
CODESYS_PATH = str(APP_CONFIG.codesys_path)
SCRIPT_DIR = str(APP_CONFIG.script_dir)
PERSISTENT_SCRIPT = str(APP_CONFIG.persistent_script)
API_KEY_FILE = str(APP_CONFIG.api_key_file)
REQUEST_DIR = str(APP_CONFIG.request_dir)
RESULT_DIR = str(APP_CONFIG.result_dir)
TERMINATION_SIGNAL_FILE = str(APP_CONFIG.termination_signal_file)
STATUS_FILE = str(APP_CONFIG.status_file)
LOG_FILE = str(APP_CONFIG.log_file)
TRANSPORT_NAME = APP_CONFIG.transport_name
PIPE_NAME = APP_CONFIG.pipe_name

# Ensure directories exist with proper permissions
def ensure_directory(path):
    """Ensure directory exists with proper permissions."""
    if not os.path.exists(path):
        try:
            os.makedirs(path)
            logger.info("Created directory: %s", path)
        except Exception as e:
            logger.error("Error creating directory %s: %s", path, str(e))
            raise
    
    # Check if directory is writable
    if not os.access(path, os.W_OK):
        logger.error("Directory %s is not writable", path)
        raise PermissionError("Directory {} is not writable".format(path))
    
    return path

# Create necessary directories
ensure_directory(REQUEST_DIR)
ensure_directory(RESULT_DIR)
temp_dir = tempfile.gettempdir()
ensure_directory(temp_dir)
class ScriptExecutor:
    """Executes scripts through the CODESYS persistent session."""
    
    def __init__(self, transport: Any):
        self.transport = transport
        
    def execute_script(self, script_content, timeout=60):
        """Execute a script and return the result.
        
        Args:
            script_content (str): The script content to execute
            timeout (int): Timeout in seconds (default: 60 seconds)
            
        Returns:
            dict: The result of the script execution
        """
        try:
            # Log script execution start with more info
            request_id = str(uuid.uuid4())
            logger.info("Executing script (request ID: %s, timeout: %s seconds)", request_id, timeout)
            script_preview = script_content[:500].replace('\n', ' ')
            logger.info("Script preview: %s...", script_preview)
            result = self.transport.execute_script(script_content, timeout=timeout)
            if result.get('success', False):
                logger.info("Script execution successful")
            else:
                logger.warning(
                    "Script execution failed via transport=%s stage=%s retryable=%s: %s",
                    result.get('transport', getattr(self.transport, 'transport_name', 'unknown')),
                    result.get('error_stage', 'unknown'),
                    result.get('retryable', 'n/a'),
                    result.get('error', 'Unknown error'),
                )
            return result
        except Exception as e:
            logger.error("Error executing script: %s", str(e))
            logger.error(traceback.format_exc())
            return {"success": False, "error": str(e)}

class CodesysApiHandler(BaseHTTPRequestHandler):
    """HTTP request handler for CODESYS API."""
    
    server_version = "CodesysApiServer/0.1"
    
    def __init__(self, *args, **kwargs):
        self.process_manager = kwargs.pop('process_manager', None)
        self.script_executor = kwargs.pop('script_executor', None)
        self.engine_adapter = kwargs.pop('engine_adapter', None)
        self.api_key_manager = kwargs.pop('api_key_manager', None)
        self.actions_service = kwargs.pop('actions_service', None)
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)
        
    def do_GET(self):
        """Handle GET requests."""
        try:
            # Parse URL
            parsed_url = urlparse.urlparse(self.path)
            path = parsed_url.path.strip('/')
            query = urlparse.parse_qs(parsed_url.query)
            
            # Single-value query params
            params = {}
            for key, values in query.items():
                if values:
                    params[key] = values[0]
                    
            # Check authentication
            if not self.authenticate():
                self.send_error(401, "Unauthorized")
                return
                
            # Route request
            if path == "api/v1/session/status":
                self.handle_session_status()
            elif path == "api/v1/project/list":
                self.handle_project_list()
            elif path == "api/v1/pou/list":
                self.handle_pou_list(params)
            elif path == "api/v1/system/info":
                self.handle_system_info()
            elif path == "api/v1/system/logs":
                self.handle_system_logs()
            else:
                self.send_error(404, "Not Found")
        except ConnectionAbortedError as e:
            logger.warning("Connection aborted during GET request: %s", str(e))
            # Don't try to send an error response as the connection is already broken
        except BrokenPipeError as e:
            logger.warning("Broken pipe during GET request: %s", str(e))
            # Don't try to send an error response as the connection is already broken
        except ConnectionResetError as e:
            logger.warning("Connection reset during GET request: %s", str(e))
            # Don't try to send an error response as the connection is already broken
        except Exception as e:
            logger.error("Error handling GET request: %s", str(e))
            try:
                self.send_error(500, str(e))
            except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
                # Connection already closed, can't send error
                pass
            
    def do_POST(self):
        """Handle POST requests."""
        try:
            # Parse URL
            parsed_url = urlparse.urlparse(self.path)
            path = parsed_url.path.strip('/')
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            
            # Python 3 compatibility for reading binary data
            if sys.version_info[0] >= 3:
                post_data = self.rfile.read(content_length).decode('utf-8')
            else:
                post_data = self.rfile.read(content_length)
            
            params = {}
            if content_length > 0:
                params = json.loads(post_data)
                
            # Check authentication
            if not self.authenticate():
                self.send_error(401, "Unauthorized")
                return
                
            # Route request
            if path == "api/v1/session/start":
                self.handle_session_start()
            elif path == "api/v1/session/stop":
                self.handle_session_stop()
            elif path == "api/v1/session/restart":
                self.handle_session_restart()
            elif path == "api/v1/project/create":
                self.handle_project_create(params)
            elif path == "api/v1/project/open":
                self.handle_project_open(params)
            elif path == "api/v1/project/save":
                self.handle_project_save()
            elif path == "api/v1/project/close":
                self.handle_project_close()
            elif path == "api/v1/project/compile":
                self.handle_project_compile(params)
            elif path == "api/v1/pou/create":
                self.handle_pou_create(params)
            elif path == "api/v1/pou/code":
                self.handle_pou_code(params)
            elif path == "api/v1/script/execute":
                self.handle_script_execute(params)
            else:
                self.send_error(404, "Not Found")
        except ConnectionAbortedError as e:
            logger.warning("Connection aborted during POST request: %s", str(e))
            # Don't try to send an error response as the connection is already broken
        except BrokenPipeError as e:
            logger.warning("Broken pipe during POST request: %s", str(e))
            # Don't try to send an error response as the connection is already broken
        except ConnectionResetError as e:
            logger.warning("Connection reset during POST request: %s", str(e))
            # Don't try to send an error response as the connection is already broken
        except Exception as e:
            logger.error("Error handling POST request: %s", str(e))
            try:
                self.send_error(500, str(e))
            except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
                # Connection already closed, can't send error
                pass
            
    def authenticate(self):
        """Validate API key."""
        auth_header = self.headers.get('Authorization', '')
        
        if auth_header.startswith('ApiKey '):
            api_key = auth_header[7:]  # Remove 'ApiKey ' prefix
            return self.api_key_manager.validate_key(api_key)
            
        return False
        
    def send_json_response(self, data, status=200):
        """Send JSON response."""
        try:
            response = json.dumps(data)
            
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            
            # Python 3 compatibility for content length
            if sys.version_info[0] >= 3:
                self.send_header('Content-Length', len(response.encode('utf-8')))
            else:
                self.send_header('Content-Length', len(response))
                
            self.end_headers()
            
            # Python 3 compatibility for writing binary data
            if sys.version_info[0] >= 3:
                self.wfile.write(response.encode('utf-8'))
            else:
                self.wfile.write(response)
        except ConnectionAbortedError as e:
            logger.warning("Connection aborted while sending response: %s", str(e))
        except BrokenPipeError as e:
            logger.warning("Broken pipe while sending response: %s", str(e))
        except ConnectionResetError as e:
            logger.warning("Connection reset while sending response: %s", str(e))
        except Exception as e:
            logger.error("Error sending JSON response: %s", str(e))
        
    # Handler methods
    
    def handle_session_start(self):
        """Handle session/start endpoint."""
        try:
            result = self.actions_service.execute(
                ActionRequest(
                    action=ActionType.SESSION_START,
                    params={},
                    request_id=str(uuid.uuid4()),
                )
            )
            self.send_json_response(result.body, result.status_code)
                
        except Exception as e:
            logger.error("Unhandled error in session start: %s", str(e), exc_info=True)
            self.send_json_response({
                "success": False,
                "error": f"Internal server error: {str(e)}"
            }, 500)
            
    def handle_session_stop(self):
        """Handle session/stop endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.SESSION_STOP,
                params={},
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
    def handle_session_restart(self):
        """Handle session/restart endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.SESSION_RESTART,
                params={},
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
            
    def handle_session_status(self):
        """Handle session/status endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.SESSION_STATUS,
                params={},
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
    def handle_project_create(self, params):
        """Handle project/create endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.PROJECT_CREATE,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
    def handle_project_open(self, params):
        """Handle project/open endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.PROJECT_OPEN,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_project_save(self):
        """Handle project/save endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.PROJECT_SAVE,
                params={},
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_project_close(self):
        """Handle project/close endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.PROJECT_CLOSE,
                params={},
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_project_list(self):
        """Handle project/list endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.PROJECT_LIST,
                params={},
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_project_compile(self, params):
        """Handle project/compile endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.PROJECT_COMPILE,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
    def handle_pou_create(self, params):
        """Handle pou/create endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.POU_CREATE,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_pou_code(self, params):
        """Handle pou/code endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.POU_CODE,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_pou_list(self, params):
        """Handle pou/list endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.POU_LIST,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
        
    def handle_script_execute(self, params):
        """Handle script/execute endpoint."""
        result = self.actions_service.execute(
            ActionRequest(
                action=ActionType.SCRIPT_EXECUTE,
                params=params,
                request_id=str(uuid.uuid4()),
            )
        )
        self.send_json_response(result.body, result.status_code)
        
    def handle_system_info(self):
        """Handle system/info endpoint."""
        info = {
            "version": "0.1",
            "process_manager": {
                "status": self.process_manager.is_running()
            },
            "codesys_path": CODESYS_PATH,
            "persistent_script": PERSISTENT_SCRIPT,
            "transport": TRANSPORT_NAME,
            "pipe_name": PIPE_NAME,
        }
        
        self.send_json_response({
            "success": True,
            "info": info
        })
        
    def handle_system_logs(self):
        """Handle system/logs endpoint."""
        logs = []
        
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r') as f:
                    logs = f.readlines()
            except:
                pass
                
        self.send_json_response({
            "success": True,
            "logs": logs
        })


def run_server():
    """Run the HTTP server."""
    try:
        # Create managers
        process_config = ProcessManagerConfig(
            codesys_path=Path(CODESYS_PATH),
            script_path=Path(PERSISTENT_SCRIPT),
            status_file=Path(STATUS_FILE),
            termination_signal_file=Path(TERMINATION_SIGNAL_FILE),
            log_file=Path(LOG_FILE),
            script_lib_dir=Path(SCRIPT_DIR) / "ScriptLib",
            profile_name=APP_CONFIG.codesys_profile_name,
            profile_path=APP_CONFIG.codesys_profile_path,
            no_ui=APP_CONFIG.codesys_no_ui,
            transport_name=APP_CONFIG.transport_name,
            pipe_name=APP_CONFIG.pipe_name,
        )
        process_manager = CodesysProcessManager(process_config, logger=logger)
        transport = build_script_transport(
            transport_name=APP_CONFIG.transport_name,
            request_dir=APP_CONFIG.request_dir,
            result_dir=APP_CONFIG.result_dir,
            temp_root=Path(tempfile.gettempdir()),
            pipe_name=APP_CONFIG.pipe_name,
        )
        script_executor = ScriptExecutor(transport)
        engine_adapter = IronPythonScriptEngineAdapter(
            codesys_path=Path(CODESYS_PATH),
            logger=logger,
        )
        api_key_manager = ApiKeyManager(Path(API_KEY_FILE))
        actions_service = ActionService(
            process_manager=process_manager,
            script_executor=script_executor,
            engine_adapter=engine_adapter,
            logger=logger,
            now_fn=time.time,
            script_dir=Path(SCRIPT_DIR),
        )
        
        # Create server
        def handler(*args):
            return CodesysApiHandler(
                process_manager=process_manager,
                script_executor=script_executor,
                engine_adapter=engine_adapter,
                api_key_manager=api_key_manager,
                actions_service=actions_service,
                *args
            )
            
        server = HTTPServer((SERVER_HOST, SERVER_PORT), handler)
        
        print("Starting server on {0}:{1}".format(SERVER_HOST, SERVER_PORT))
        logger.info("Starting server on %s:%d", SERVER_HOST, SERVER_PORT)
        
        # Run server
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server stopped")
    except Exception as e:
        print("Error starting server: " + str(e))
        logger.error("Error starting server: %s", str(e))
    finally:
        # Stop CODESYS process
        if 'process_manager' in locals():
            process_manager.stop()
            

if __name__ == "__main__":
    run_server()
