"""
IronPython 2.7 script fragment builders for CODESYS scriptengine primitives.

Each function here is backed by a passing real-CODESYS probe.
``ironpython_script_engine.py`` must only use primitives from this module
when generating CODESYS-facing scripts.

Do NOT add a function here unless the corresponding probe has passed against
real CODESYS.  See docs/CODESYS_BOUNDARY_CONTRACT.md.

Probe → Function mapping
------------------------
real_project_create_direct_raw_probe    build_create_empty_project_fragment
real_project_skeleton_probe  step 2     build_add_device_fragment
real_project_skeleton_probe  step 3     build_resolve_active_application_fragment
real_project_skeleton_probe  step 4     build_create_pou_fragment
real_project_skeleton_probe  step 5     build_create_task_configuration_fragment
real_project_skeleton_probe  step 6     build_create_main_task_fragment
real_project_skeleton_probe  step 7     build_assign_pou_to_task_fragment
"""

from __future__ import annotations


def _escape(value: str) -> str:
    """Escape a value for embedding in an IronPython double-quoted string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def build_create_empty_project_fragment(path: str) -> str:
    """
    IronPython line: create an empty project at *path*.

    Proven fact: ``scriptengine.projects.create(path, True)`` succeeds in the
    real environment and returns a project object.  The created project is
    intentionally minimal — no device, no application, no PLC_PRG.

    Assigns to ``project`` (caller's local variable).
    """
    return 'project = scriptengine.projects.create("{0}", True)'.format(_escape(path))


def build_add_device_fragment(
    name: str,
    type_: int,
    device_id: str,
    version: str,
) -> str:
    """
    IronPython line: add a device to the open project.

    Proven facts:
    - ``project.add()`` is a side-effect call — it returns ``None``.
    - After this call the device is present in ``project.get_children()``.
    - ``project.active_application`` is automatically populated once the
      device is added (no explicit assignment required).

    Assumes ``project`` (local variable) is set.
    """
    return 'project.add("{0}", {1}, "{2}", "{3}")'.format(
        _escape(name), type_, _escape(device_id), _escape(version)
    )


def build_resolve_active_application_fragment() -> str:
    """
    IronPython line: read the active application that was auto-created by
    ``add_device``.

    Proven fact: after ``project.add()`` the ``project.active_application``
    property is non-None and ready for POU / task operations.

    Assigns to ``app`` (caller's local variable).
    """
    return "app = project.active_application"


def build_create_pou_fragment(pou_name: str) -> str:
    """
    IronPython line: create a Program POU in the active application.

    Proven fact: ``app.create_pou(name=..., type=PouType.Program,
    language=ImplementationLanguages.st)`` succeeds and returns a non-None
    POU object.

    Assumes ``app`` (local variable) is set.
    Assigns to ``existing_program`` (caller's local variable).
    """
    return (
        'existing_program = app.create_pou('
        'name="{0}", '
        'type=scriptengine.PouType.Program, '
        'language=scriptengine.ImplementationLanguages.st)'
    ).format(_escape(pou_name))


def build_create_task_configuration_fragment() -> str:
    """
    IronPython line: create a task configuration in the active application.

    Proven fact: ``app.create_task_configuration()`` succeeds and returns a
    non-None task config object.

    Assumes ``app`` (local variable) is set.
    Assigns to ``task_config`` (caller's local variable).
    """
    return "task_config = app.create_task_configuration()"


def build_create_main_task_fragment(task_name: str) -> str:
    """
    IronPython line: create a named task inside the task configuration.

    Proven fact: ``task_config.create_task(name)`` succeeds and returns a
    non-None task object.

    Assumes ``task_config`` (local variable) is set.
    Assigns to ``existing_task`` (caller's local variable).
    """
    return 'existing_task = task_config.create_task("{0}")'.format(_escape(task_name))


def build_assign_pou_to_task_fragment(pou_name: str) -> str:
    """
    IronPython line: assign a POU to the task by name.

    Proven fact: ``existing_task.pous.add(pou_name)`` succeeds and the POU
    name appears in ``task.pous`` afterwards.

    Assumes ``existing_task`` (local variable) is set.
    """
    return 'existing_task.pous.add("{0}")'.format(_escape(pou_name))
