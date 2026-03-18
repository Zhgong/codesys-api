from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from engine_adapter import EngineCapabilities, ExecutionSpec


class IronPythonScriptEngineAdapter:
    """Generate IronPython-compatible scripts for the current CODESYS scriptengine."""

    def __init__(self, *, codesys_path: Path, logger: logging.Logger) -> None:
        self.codesys_path = codesys_path
        self.logger = logger

    @property
    def engine_name(self) -> str:
        return "codesys-ironpython-scriptengine"

    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities(
            session_start=True,
            session_status=True,
            script_execute=True,
            project_create=True,
            project_open=True,
            project_save=True,
            project_close=True,
            project_list=True,
            project_compile=True,
            pou_create=True,
            pou_code=True,
            pou_list=True,
        )

    def build_execution(self, action: str, params: dict[str, object]) -> ExecutionSpec:
        if action == "session.start":
            return ExecutionSpec(script=self._generate_session_start_script(), timeout=60)
        if action == "session.status":
            return ExecutionSpec(script=self._generate_session_status_script(), timeout=60)
        if action == "script.execute":
            script = params.get("script")
            if not isinstance(script, str) or not script:
                raise ValueError("Missing required parameter: script")
            return ExecutionSpec(script=script, timeout=60)
        if action == "project.create":
            return ExecutionSpec(script=self._generate_project_create_script(params), timeout=30)
        if action == "project.open":
            return ExecutionSpec(script=self._generate_project_open_script(params), timeout=30)
        if action == "project.save":
            return ExecutionSpec(script=self._generate_project_save_script(), timeout=30)
        if action == "project.close":
            return ExecutionSpec(script=self._generate_project_close_script(), timeout=30)
        if action == "project.list":
            return ExecutionSpec(script=self._generate_project_list_script(), timeout=30)
        if action == "project.compile":
            return ExecutionSpec(script=self._generate_project_compile_script(params), timeout=120)
        if action == "pou.create":
            return ExecutionSpec(script=self._generate_pou_create_script(params), timeout=30)
        if action == "pou.code":
            return ExecutionSpec(script=self._generate_pou_code_script(params), timeout=30)
        if action == "pou.list":
            return ExecutionSpec(script=self._generate_pou_list_script(params), timeout=30)

        raise ValueError("Unsupported action for engine adapter: {0}".format(action))

    def normalize_result(self, action: str, raw_result: dict[str, Any]) -> dict[str, object]:
        normalized = dict(raw_result)
        if "success" not in normalized:
            normalized["success"] = False
            normalized["error"] = "Engine result missing success flag for action: {0}".format(action)
        if normalized.get("success") is False and "error" not in normalized:
            normalized["error"] = "Engine action failed: {0}".format(action)
        return normalized

    def _generate_session_start_script(self) -> str:
        return """
import scriptengine
import json
import sys
import warnings

# Silence deprecation warnings for sys.exc_clear() in IronPython 2.7
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    # Use the global system instance provided by scriptengine
    # IMPORTANT: scriptengine.system is a pre-existing instance
    print("Using global scriptengine.system instance")
    system = scriptengine.system
    
    # Store system instance
    session.system = system
    
    # Return success
    result = {"success": True, "message": "Session started"}
except:
    # IronPython 2.7 style exception handling (no 'as e' syntax)
    error_type, error_value, error_traceback = sys.exc_info()
    result = {"success": False, "error": str(error_value)}
"""

    def _generate_session_status_script(self) -> str:
        return """
import scriptengine
import json

try:
    # Get system status
    system = session.system
    
    result = {
        "success": True,
        "status": {
            "session_active": system is not None,
            "project_open": session.active_project is not None
        }
    }
    
    if session.active_project:
        result["status"]["project"] = {
            "path": session.active_project.path,
            "dirty": session.active_project.dirty
        }
except Exception as e:
    result = {"success": False, "error": str(e)}
"""

    def _generate_project_create_script(self, params: dict[str, object]) -> str:
        path = str(params.get("path", "")).replace("/", "\\")

        template_path = str(params.get("template_path", ""))
        if not template_path:
            codesys_dir = os.path.dirname(str(self.codesys_path))
            if "Common" in codesys_dir:
                codesys_dir = os.path.dirname(codesys_dir)
            template_path = os.path.join(codesys_dir, "Templates", "Standard.project")
            self.logger.info("Using derived template path: %s", template_path)

        codesys_path = str(self.codesys_path)

        return """
# Simple script to create a project from template - IronPython 2.7 compatible
import scriptengine
import json
import os
import sys
import warnings
import traceback

# Silence deprecation warnings for sys.exc_clear() in IronPython 2.7
warnings.filterwarnings("ignore", category=DeprecationWarning)

try:
    print("Starting project creation script")
    
    # Check if standard template exists at the provided path
    template_path = "{1}"
    print("Looking for template at: " + template_path)
    
    if not os.path.exists(template_path):
        print("Template not found at: " + template_path)
        
        # Try to determine template location directly from CODESYS_PATH
        codesys_path = r"{2}"
        print("CODESYS path: " + codesys_path)
        
        # Derive template path from CODESYS executable path
        codesys_dir = os.path.dirname(codesys_path)  # Get directory containing CODESYS.exe
        if "Common" in codesys_dir:  # Handle "Common" subfolder case
            codesys_dir = os.path.dirname(codesys_dir)  # Go up one level
            
        template_path = os.path.join(codesys_dir, "Templates", "Standard.project")
        print("Trying template at: " + template_path)
    
    if not os.path.exists(template_path):
        print("Template not found! Cannot create project from template.")
        raise Exception("Template not found at: " + template_path)
    
    # Simple approach: open template, save as new name
    print("Opening template: " + template_path)
    project = scriptengine.projects.open(template_path)
    if project is None:
        print("Failed to open template project")
        raise Exception("Failed to open template project at: " + template_path)
    
    print("Template opened successfully")
    
    # Save as new project name
    print("Saving as new project: {0}")
    if hasattr(project, 'save_as'):
        project.save_as("{0}")
        print("Project saved successfully as: {0}")
    else:
        print("Project has no save_as method")
        raise Exception("Project object does not have a save_as method")
    
    print("Setting as active project")
    session.active_project = project
    
    print("Checking for active application")
    if hasattr(project, 'active_application') and project.active_application is not None:
        app = project.active_application
        print("Found active application: " + str(app))
    else:
        print("No active application found in project")
    
    print("Project creation completed")
    
    result = {{
        "success": True,
        "project": {{
            "path": project.path if hasattr(project, 'path') else "{0}",
            "name": project.name if hasattr(project, 'name') else os.path.basename("{0}"),
            "dirty": project.dirty if hasattr(project, 'dirty') else False
        }}
    }}
except:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error creating project: " + str(error_value))
    print(traceback.format_exc())
    
    result = {{
        "success": False,
        "error": str(error_value)
    }}
""".format(path.replace("\\", "\\\\"), template_path.replace("\\", "\\\\"), codesys_path.replace("\\", "\\\\"))

    def _generate_project_open_script(self, params: dict[str, object]) -> str:
        path = str(params.get("path", ""))

        return """
import scriptengine
import json
import sys
import os
import traceback

try:
    print("Starting project open script")
    print("Opening project at path: {0}")
    
    if not hasattr(scriptengine, 'projects'):
        print("Global scriptengine.projects instance not found")
        result = {{"success": False, "error": "Global scriptengine.projects instance not found"}}
    else:
        try:
            print("Using global scriptengine.projects instance to open project")
            project = scriptengine.projects.open("{0}")
            
            if project is None:
                print("Project open returned None")
                result = {{"success": False, "error": "Project open operation returned None"}}
            else:
                print("Project opened successfully")
                print("Storing project as active project in session")
                session.active_project = project
                project_info = {{"path": "{0}"}}
                
                if hasattr(project, 'path'):
                    project_info['path'] = project.path
                    print("Project path: " + project.path)
                    if not hasattr(project, 'name'):
                        try:
                            project_info['name'] = os.path.basename(project.path)
                            print("Extracted name from path: " + project_info['name'])
                        except Exception:
                            project_info['name'] = os.path.basename("{0}")
                else:
                    print("Project has no path attribute, using request path")
                
                if 'name' not in project_info and hasattr(project, 'name'):
                    project_info['name'] = project.name
                    print("Project name: " + project.name)
                elif 'name' not in project_info:
                    project_info['name'] = os.path.basename("{0}")
                
                if hasattr(project, 'dirty'):
                    project_info['dirty'] = project.dirty
                    print("Project dirty state: " + str(project.dirty))
                else:
                    project_info['dirty'] = False
                
                result = {{
                    "success": True,
                    "project": project_info
                }}
        except Exception as e:
            print("Error opening project: " + str(e))
            print(traceback.format_exc())
            result = {{"success": False, "error": str(e)}}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in project open script: " + str(error_value))
    print(traceback.format_exc())
    result = {{"success": False, "error": str(error_value)}}
""".format(path.replace("\\", "\\\\"))

    def _generate_project_save_script(self) -> str:
        return """
import scriptengine
import json
import sys
import traceback

try:
    print("Starting project save script")
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session"}
    else:
        project = session.active_project
        project.save()
        result = {"success": True, "message": "Project saved successfully"}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in project save script: " + str(error_value))
    print(traceback.format_exc())
    result = {"success": False, "error": str(error_value)}
"""

    def _generate_project_close_script(self) -> str:
        return """
import scriptengine
import json
import sys
import traceback

try:
    print("Starting project close script")
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {"success": False, "error": "No active project in session"}
    else:
        project = session.active_project
        if hasattr(project, 'close'):
            project.close()
        session.active_project = None
        result = {"success": True, "message": "Project closed successfully"}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in project close script: " + str(error_value))
    print(traceback.format_exc())
    result = {"success": False, "error": str(error_value)}
"""

    def _generate_project_list_script(self) -> str:
        return """
import scriptengine
import json
import sys
import os
import traceback

try:
    print("Starting project list script")
    projects = []
    if not hasattr(scriptengine, 'projects'):
        result = {"success": False, "error": "Global scriptengine.projects instance not found"}
    else:
        try:
            recent_projects = []
            if hasattr(scriptengine.projects, 'recent_projects'):
                recent_projects = scriptengine.projects.recent_projects
            elif hasattr(scriptengine.projects, 'get_recent_projects'):
                recent_projects = scriptengine.projects.get_recent_projects()

            for project in recent_projects:
                try:
                    project_info = {"path": ""}
                    if hasattr(project, 'path'):
                        project_info["path"] = project.path
                        try:
                            project_info["name"] = os.path.basename(project.path)
                        except Exception:
                            project_info["name"] = ""
                    if hasattr(project, 'name'):
                        project_info["name"] = project.name
                    if hasattr(project, 'last_opened_date'):
                        project_info["last_opened"] = project.last_opened_date
                    projects.append(project_info)
                except Exception as project_error:
                    print("Error processing project item: " + str(project_error))

            result = {
                "success": True,
                "projects": projects
            }
        except Exception as e:
            print("Error processing projects list: " + str(e))
            print(traceback.format_exc())
            result = {"success": False, "error": "Error processing projects list: " + str(e)}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in project list script: " + str(error_value))
    print(traceback.format_exc())
    result = {"success": False, "error": str(error_value)}
"""

    def _generate_pou_create_script(self, params: dict[str, object]) -> str:
        name = str(params.get("name", ""))
        pou_type = str(params.get("type", "Program"))
        language = str(params.get("language", "ST"))

        return """
import scriptengine
import json
import sys
import traceback

try:
    print("Starting POU creation script")
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session"}}
    else:
        project = session.active_project
        app = project.active_application
        pou_type_map = {{
            "Program": scriptengine.PouType.Program,
            "FunctionBlock": scriptengine.PouType.FunctionBlock,
            "Function": scriptengine.PouType.Function
        }}
        language_map = {{
            "ST": scriptengine.ImplementationLanguages.st,
            "IL": scriptengine.ImplementationLanguages.instruction_list,
            "LD": scriptengine.ImplementationLanguages.ladder,
            "FBD": scriptengine.ImplementationLanguages.fbd,
            "SFC": scriptengine.ImplementationLanguages.sfc,
            "CFC": scriptengine.ImplementationLanguages.cfc
        }}
        language_guid = language_map.get("{2}".upper(), scriptengine.ImplementationLanguages.st)
        if hasattr(app, 'pou_container'):
            created_pou = app.pou_container.create_pou(
                name="{0}",
                type=pou_type_map["{1}"],
                language=language_guid
            )
        else:
            created_pou = app.create_pou(
                name="{0}",
                type=pou_type_map["{1}"],
                language=language_guid
            )
        if not hasattr(session, 'created_pous'):
            session.created_pous = {{}}
        session.created_pous["{0}"] = created_pou
        result = {{
            "success": True,
            "pou": {{
                "name": "{0}",
                "type": "{1}",
                "language": "{2}"
            }}
        }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in POU creation script: " + str(error_value))
    print(traceback.format_exc())
    result = {{"success": False, "error": str(error_value)}}
""".format(name, pou_type, language)

    def _generate_pou_code_script(self, params: dict[str, object]) -> str:
        path = str(params.get("path", ""))
        declaration = str(params.get("declaration", ""))
        implementation = str(params.get("implementation", ""))
        code = str(params.get("code", ""))

        return """
import scriptengine
import json
import sys
import traceback

try:
    print("Starting POU code setting script for {0}")
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session"}}
    else:
        project = session.active_project
        target = None
        target_name = "{0}".split("/")[-1]
        if hasattr(session, 'created_pous'):
            target = session.created_pous.get(target_name)
        if target is None:
            search_result = project.find("{0}")
            if search_result is not None:
                if hasattr(search_result, 'textual_declaration') or hasattr(search_result, 'set_implementation_code'):
                    target = search_result
                elif hasattr(search_result, '__iter__'):
                    for candidate in search_result:
                        if hasattr(candidate, 'textual_declaration') or hasattr(candidate, 'set_implementation_code'):
                            target = candidate
                            break
        if target is None:
            result = {{"success": False, "error": "POU not found: {0}"}}
        else:
            if "{1}":
                target.textual_declaration.replace(new_text="{1}")
            if "{2}":
                target.textual_implementation.replace(new_text="{2}")
            if "{3}" and not "{1}" and not "{2}":
                if hasattr(target, 'set_implementation_code'):
                    target.set_implementation_code("{3}")
                else:
                    target.textual_implementation.replace(new_text="{3}")
            result = {{"success": True, "message": "POU code updated successfully"}}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in POU code script: " + str(error_value))
    print(traceback.format_exc())
    result = {{"success": False, "error": str(error_value)}}
""".format(
            path.replace("\\", "\\\\"),
            declaration.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"),
            implementation.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"),
            code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n"),
        )

    def _generate_pou_list_script(self, params: dict[str, object]) -> str:
        parent_path = str(params.get("parentPath", "Application"))

        return """
import scriptengine
import json
import sys
import traceback

try:
    print("Starting POU listing script")
    container_name = "{0}"
    if not hasattr(session, 'active_project') or session.active_project is None:
        result = {{"success": False, "error": "No active project in session"}}
    else:
        project = session.active_project
        container = project.find(container_name)
        if container is None:
            result = {{"success": False, "error": "Container not found: " + container_name}}
        else:
            pous = []
            if hasattr(container, 'get_children'):
                for obj in container.get_children():
                    try:
                        if hasattr(obj, 'type') and hasattr(obj, 'name'):
                            pous.append({{
                                "name": str(obj.name),
                                "type": str(obj.type).split('.')[-1],
                                "language": "Unknown"
                            }})
                    except Exception as obj_error:
                        print("Error processing object: " + str(obj_error))

            if hasattr(session, 'created_pous') and session.created_pous:
                for pou_name, pou_obj in session.created_pous.items():
                    already_listed = False
                    for existing_pou in pous:
                        if existing_pou.get("name") == pou_name:
                            already_listed = True
                            break
                    if not already_listed:
                        pous.append({{
                            "name": pou_name,
                            "type": str(getattr(pou_obj, 'type', 'Unknown')).split('.')[-1],
                            "language": "Unknown",
                            "source": "session_cache"
                        }})

            result = {{
                "success": True,
                "pous": pous,
                "container": container_name
            }}
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in POU listing script: " + str(error_value))
    print(traceback.format_exc())
    result = {{"success": False, "error": str(error_value)}}
""".format(parent_path)

    def _generate_project_compile_script(self, params: dict[str, object]) -> str:
        clean_build = bool(params.get("clean_build", False))

        return """
import scriptengine
import json
import sys
import traceback

try:
    print("Starting project compilation script")
    clean_build = {0}
    print("Clean build: " + str(clean_build))
    
    if not hasattr(session, 'active_project') or session.active_project is None:
        print("No active project in session")
        result = {{"success": False, "error": "No active project in session"}}
    else:
        project = session.active_project
        print("Got active project: " + str(project.path))
        
        if not hasattr(project, 'active_application') or project.active_application is None:
            print("Project has no active application")
            result = {{"success": False, "error": "Project has no active application"}}
        else:
            application = project.active_application
            print("Got active application")
            system = session.system if hasattr(session, 'system') else None
            if system is None and hasattr(scriptengine, 'system'):
                system = scriptengine.system
            if system is not None and hasattr(system, 'clear_messages'):
                try:
                    system.clear_messages()
                    print("Cleared previous messages")
                except Exception as clear_e:
                    print("Warning: Could not clear messages: " + str(clear_e))
            
            try:
                print("Starting compilation...")
                
                if clean_build:
                    if hasattr(application, 'rebuild'):
                        print("Performing rebuild...")
                        application.rebuild()
                    else:
                        print("Rebuild method not available, using build instead")
                        application.build()
                else:
                    print("Performing build...")
                    application.build()
                
                print("Build command completed")
                compilation_messages = []
                if system is not None and hasattr(system, 'get_messages'):
                    try:
                        messages = system.get_messages()
                        print("Retrieved " + str(len(messages)) + " compilation messages")
                        for msg in messages:
                            compilation_messages.append({{
                                "text": str(msg),
                                "level": "info"
                            }})
                    except Exception as msg_e:
                        print("Warning: Could not get compilation messages: " + str(msg_e))
                
                if system is not None and hasattr(system, 'get_message_objects'):
                    try:
                        message_objects = system.get_message_objects()
                        print("Retrieved " + str(len(message_objects)) + " message objects")
                        for msg_obj in message_objects:
                            try:
                                msg_text = str(msg_obj)
                                msg_level = "info"
                                if hasattr(msg_obj, 'severity'):
                                    severity = str(msg_obj.severity).lower()
                                    if 'error' in severity:
                                        msg_level = "error"
                                    elif 'warning' in severity:
                                        msg_level = "warning"
                                
                                compilation_messages.append({{
                                    "text": msg_text,
                                    "level": msg_level
                                }})
                            except Exception as parse_msg_e:
                                print("Warning: Could not parse message object: " + str(parse_msg_e))
                    except Exception as msg_obj_e:
                        print("Warning: Could not get message objects: " + str(msg_obj_e))
                
                has_errors = any(msg.get("level") == "error" for msg in compilation_messages)
                
                if has_errors:
                    print("Compilation completed with errors")
                    result = {{
                        "success": False,
                        "error": "Compilation completed with errors",
                        "messages": compilation_messages,
                        "build_type": "rebuild" if clean_build else "build"
                    }}
                else:
                    print("Compilation completed successfully")
                    result = {{
                        "success": True,
                        "message": "Project compiled successfully",
                        "messages": compilation_messages,
                        "build_type": "rebuild" if clean_build else "build"
                    }}
                    
            except Exception as build_e:
                print("Error during build: " + str(build_e))
                print(traceback.format_exc())
                result = {{
                    "success": False,
                    "error": "Compilation failed: " + str(build_e),
                    "build_type": "rebuild" if clean_build else "build"
                }}
                
except Exception:
    error_type, error_value, error_traceback = sys.exc_info()
    print("Error in project compilation script: " + str(error_value))
    print(traceback.format_exc())
    result = {{"success": False, "error": str(error_value)}}
""".format("True" if clean_build else "False")
