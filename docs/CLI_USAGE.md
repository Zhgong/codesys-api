# CLI Usage

## Summary

The repository now provides a local CLI entrypoint on top of the shared action layer.

Supported entrypoints:

- `codesys-cli ...`
- `codesys-api-server ...`
- `python codesys_cli.py ...`
- `run_cli.bat ...`

The CLI talks directly to the local runtime wiring. It does not call the HTTP API.

Current contract:

- `named_pipe` only
- default output is human-readable text
- `--json` returns raw structured results
- exit codes are `0` for success, `1` for business/runtime failure, and `2` for setup/input error

Built-in help:

- `codesys-cli --help`
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
- `CODESYS_API_CODESYS_NO_UI` is opt-in
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

- `codesys-cli session start`
- `codesys-cli session restart`
- `codesys-cli session status`
- `codesys-cli session stop`
- `python codesys_cli.py session start`
- `python codesys_cli.py session restart`
- `python codesys_cli.py session status`
- `python codesys_cli.py session stop`

Project:

- `codesys-cli project create --path C:\work\demo.project`
- `codesys-cli project open --path C:\work\demo.project`
- `codesys-cli project save`
- `codesys-cli project close`
- `codesys-cli project list`
- `codesys-cli project compile`
- `codesys-cli project compile --clean-build`
- `python codesys_cli.py project create --path C:\work\demo.project`
- `python codesys_cli.py project open --path C:\work\demo.project`
- `python codesys_cli.py project save`
- `python codesys_cli.py project close`
- `python codesys_cli.py project list`
- `python codesys_cli.py project compile`
- `python codesys_cli.py project compile --clean-build`

POU:

- `codesys-cli pou create --name MotorController --type FunctionBlock --language ST`
- `codesys-cli pou list`
- `codesys-cli pou list --parent-path Application`
- `codesys-cli pou code --path Application\PLC_PRG --implementation-file plc_prg_impl.txt`
- `codesys-cli pou code --path Application\MotorController --declaration-file decl.txt --implementation-file impl.txt`
- `python codesys_cli.py pou create --name MotorController --type FunctionBlock --language ST`
- `python codesys_cli.py pou list`
- `python codesys_cli.py pou list --parent-path Application`
- `python codesys_cli.py pou code --path Application\PLC_PRG --implementation-file plc_prg_impl.txt`
- `python codesys_cli.py pou code --path Application\MotorController --declaration-file decl.txt --implementation-file impl.txt`

## Typical Flow

```powershell
codesys-cli session start
codesys-cli project create --path C:\work\demo.project
codesys-cli pou create --name MotorController --type FunctionBlock --language ST
codesys-cli pou list
codesys-cli project save
codesys-cli project compile
codesys-cli project close
codesys-cli session stop
```

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
codesys-cli pou code --path Application\PLC_PRG --implementation-file broken_impl.txt
codesys-cli project compile
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
codesys-cli --json project compile
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
- After project-based validation flows, close the project before stopping the session to avoid IDE-side project locks.
