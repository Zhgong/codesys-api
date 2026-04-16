# CLI Usage

## Summary

The repository now provides a local CLI entrypoint on top of the shared action layer.
The CLI is a convenience wrapper; the HTTP server is the primary workflow for persistent multi-step session usage.

Supported entrypoints:

- `codesys-tools ...`
- `codesys-tools-server ...`
- `python codesys_cli.py ...`
- `run_cli.bat ...`

The CLI talks directly to the local runtime wiring. It does not call the HTTP API.

Important:

- each CLI invocation executes one action
- reuse the same `CODESYS_API_PIPE_NAME` when you want later CLI commands to attach to the same CODESYS session
- use `codesys-tools-server` when you want the primary persistent-session workflow

Current contract:

- `named_pipe` only
- default output is human-readable text
- `--json` returns raw structured results
- exit codes are `0` for success, `1` for business/runtime failure, and `2` for setup/input error

Built-in help:

- `codesys-tools --help`
- `python codesys_cli.py --help`
- `python codesys_cli.py session --help`
- `python codesys_cli.py project --help`
- `python codesys_cli.py pou --help`

## Environment

The CLI uses the same environment variables as the server runtime.

Required on this machine:

- `CODESYS_API_CODESYS_PATH`
- `CODESYS_API_CODESYS_PROFILE`
- `CODESYS_API_CODESYS_PROFILE_PATH`

Important runtime assumptions:

- only `named_pipe` is supported
- `CODESYS_API_CODESYS_NO_UI=1` is recommended for headless server workflows
- project creation uses the validated default SoftPLC automatically

Example:

```powershell
$env:CODESYS_API_CODESYS_PATH="C:\Program Files\CODESYS 3.5.20.50\CODESYS\Common\CODESYS.exe"
$env:CODESYS_API_CODESYS_PROFILE="CODESYS V3.5 SP20 Patch 5"
$env:CODESYS_API_CODESYS_PROFILE_PATH="C:\Program Files\CODESYS 3.5.20.50\CODESYS\Profiles\CODESYS V3.5 SP20 Patch 5.profile.xml"
$env:CODESYS_API_TRANSPORT="named_pipe"
```

## Commands

Session:

- `codesys-tools session start`
- `codesys-tools session restart`
- `codesys-tools session status`
- `codesys-tools session stop`
- `python codesys_cli.py session start`
- `python codesys_cli.py session restart`
- `python codesys_cli.py session status`
- `python codesys_cli.py session stop`

Project:

- `codesys-tools project create --path C:\work\demo.project`
- `codesys-tools project open --path C:\work\demo.project`
- `codesys-tools project save`
- `codesys-tools project close`
- `codesys-tools project list`
- `codesys-tools project compile`
- `codesys-tools project compile --clean-build`
- `python codesys_cli.py project create --path C:\work\demo.project`
- `python codesys_cli.py project open --path C:\work\demo.project`
- `python codesys_cli.py project save`
- `python codesys_cli.py project close`
- `python codesys_cli.py project list`
- `python codesys_cli.py project compile`
- `python codesys_cli.py project compile --clean-build`

Current project contract:

- `project create` creates and opens a project as the active project
- if another project is already active, `project create` fails instead of replacing it
- close the current project first when you want to create another one

POU:

- `codesys-tools pou create --name MotorController --type FunctionBlock --language ST`
- `codesys-tools pou list`
- `codesys-tools pou list --parent-path Application`
- `codesys-tools pou code --path CounterFB --implementation-file plc_prg_impl.txt`
- `codesys-tools pou code --path Application\MotorController --declaration-file decl.txt --implementation-file impl.txt`
- `python codesys_cli.py pou create --name MotorController --type FunctionBlock --language ST`
- `python codesys_cli.py pou list`
- `python codesys_cli.py pou list --parent-path Application`
- `python codesys_cli.py pou code --path Application\PLC_PRG --implementation-file plc_prg_impl.txt`
- `python codesys_cli.py pou code --path Application\MotorController --declaration-file decl.txt --implementation-file impl.txt`

## Typical Flow

```powershell
codesys-tools-server
```

For multi-step workflows, either reuse the same `CODESYS_API_PIPE_NAME` across CLI invocations or use the HTTP server.

Repo-local compatibility:

```powershell
python codesys_cli.py session start
python codesys_cli.py project create --path C:\work\demo.project
python codesys_cli.py pou create --name MotorController --type FunctionBlock --language ST
python codesys_cli.py pou list
python codesys_cli.py project save
python codesys_cli.py project compile
python codesys_cli.py project close
python codesys_cli.py session stop
```

## Negative Compile Example

To confirm compile failure handling, write invalid implementation code into `Application\PLC_PRG` and compile:

```powershell
codesys-tools pou code --path Application\PLC_PRG --implementation-file broken_impl.txt
codesys-tools project compile
```

Repo-local compatibility:

```powershell
python codesys_cli.py pou code --path Application\PLC_PRG --implementation-file broken_impl.txt
python codesys_cli.py project compile
```

The current stable negative sample is an implementation containing:

```text
MissingVar := TRUE;
```

## Output And Exit Codes

Default output is human-readable.

Use `--json` for raw structured results:

```powershell
codesys-tools --json project compile
```

Repo-local compatibility:

```powershell
python codesys_cli.py --json project compile
```

Exit codes:

- `0` success
- `1` business or runtime failure
- `2` argument or input-file error

## Common Setup Errors

The CLI now performs a small preflight check before building the runtime.

Typical setup failures:

- `CODESYS profile is not configured`
  - set `CODESYS_API_CODESYS_PROFILE` or `CODESYS_API_CODESYS_PROFILE_PATH`
- `CODESYS executable not found`
  - fix `CODESYS_API_CODESYS_PATH`
- `Unsupported transport 'file'`
  - the CLI supports `named_pipe` only

These failures return exit code `2`.

## Notes

- `project list` uses the current CODESYS recent-projects API and may legitimately return an empty list.
- `pou/code --path` accepts bare names and tree paths with `/` or `\`.
- `project/compile` may restart CODESYS in UI mode temporarily when `CODESYS_API_CODESYS_NO_UI=1`.
- POU declarations sent via `pou/code` must omit the `FUNCTION_BLOCK` / `PROGRAM` header line.
- After project-based validation flows, close the project before stopping the session to avoid IDE-side project locks.
