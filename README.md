# CODESYS REST API

## Repository Layout

The repository is in the middle of a compatibility-first reorganization:

- root entrypoints such as `HTTP_SERVER.py`, `codesys_cli.py`, and `run_cli.bat` remain usable
- core host-side implementation is moving into `src/codesys_api/`
- long-lived documentation is moving into `docs/`
- debug and diagnostic helpers are moving into `scripts/debug/`
- runtime stub assets now live under `codesys_assets/`

Use `BASELINE.md` and `python scripts\\run_baseline.py` before and after structural changes.

![CODESYS API Logo](https://via.placeholder.com/1200x300/0073CF/FFFFFF?text=CODESYS+REST+API)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

本项目旨在提供一个极速、有状态且极具大模型友好性（LLM-Friendly）的 CODESYS 命令行接口。通过在后台维护持久化的 CODESYS 会话，它不仅消除了传统脚本的启动延迟，还通过极简的 CLI 抽象层，让 AI 代理和 CI/CD 流水线能够以极低的 Token 成本和极高的稳定性自动化生成、测试和编译 PLC 控制逻辑，并为未来无缝迁移至 CODESYS Scripting 4.2.0 奠定架构基础。

## 🎯 核心愿景 (Core Vision)

1. **核心定位 (Core Positioning):** 打造 AI 原生（AI-Native）的极速工业编程接口，以“零协议开销”降低 Token 消耗并提升大模型直接控制 CODESYS 环境的成功率。
2. **性能目的 (Performance Goal):** 实现“毫秒级”的持久化状态交互，彻底消除 CODESYS 每次执行脚本时的冷启动过程等待时间。
3. **架构目的 (Architecture Goal):** 建立防过时（Future-Proof）的抽象隔离层，解耦业务逻辑与底层环境，为未来无缝切换到无用户界面的 Python 3 脚本引擎做好准备。
4. **业务目的 (Business Goal):** 填补现代 IT 与传统 OT（操作技术）的鸿沟，让传统的重型 PLC 工业软件能够无缝接入现代的 DevOps 和 CI/CD 流水线。

## 📋 Features

- **Persistent CODESYS Session**: Maintains a single running instance of CODESYS for improved performance
- **RESTful API**: Provides standard HTTP endpoints for all CODESYS operations
- **Session Management**: Start, stop, and monitor CODESYS sessions
- **Project Operations**: Create, open, save, close, and compile projects
- **POU Management**: Create and modify Program Organization Units
- **Script Execution**: Execute arbitrary CODESYS scripts
- **Authentication**: Secure access with API keys
- **Windows Service**: Run as a background service with auto-recovery
- **Comprehensive Logging**: Detailed activity and error logging

## 🚀 Quick Start

### Prerequisites

- Windows OS with CODESYS 3.5 or later installed
- Python 3.x installed
  - Note: Only the PERSISTENT_SESSION.py script maintains compatibility with CODESYS IronPython environment
- Administrator privileges (for service installation)

### Installation

1. Clone this repository:
   ```
   git clone https://github.com/johannesPettersson80/codesys-api.git
   ```

2. Navigate to the project directory:
   ```
   cd codesys-api
   ```

3. Install required packages:
   ```
   pip install requests pywin32
   ```

4. Run the installation script:
   ```
   install.bat
   ```

   If you prefer not to install as a Windows service, use:
   ```
   start_server.bat
   ```

5. Verify the installation:
   ```
   python example_client.py
   ```

For detailed installation instructions, see the [Installation Guide](INSTALLATION_GUIDE.md) and [CODESYS Script Compatibility Guide](CODESYS_SCRIPT_COMPATIBILITY.md).

## 📖 API Documentation

### Authentication

All API requests require an API key in the header:

```
Authorization: ApiKey YOUR_API_KEY
```

### Endpoints

#### Session Management

- `POST /api/v1/session/start`: Start CODESYS session
- `POST /api/v1/session/stop`: Stop CODESYS session
- `GET /api/v1/session/status`: Get session status
- `POST /api/v1/session/restart`: Restart CODESYS session

#### Project Operations

- `POST /api/v1/project/create`: Create new project
- `POST /api/v1/project/open`: Open existing project
- `POST /api/v1/project/save`: Save current project
- `POST /api/v1/project/close`: Close current project
- `POST /api/v1/project/compile`: Compile project
- `GET /api/v1/project/list`: List recent projects

#### POU Management

- `POST /api/v1/pou/create`: Create new POU
- `POST /api/v1/pou/code`: Set POU code
- `GET /api/v1/pou/list`: List POUs in project

#### Script Execution

- `POST /api/v1/script/execute`: Execute arbitrary script

#### System Operations

- `GET /api/v1/system/info`: Get system information
- `GET /api/v1/system/logs`: Get system logs

## 📝 Example Usage

### Example Client

The repository includes an example client (`example_client.py`) demonstrating basic operations:

```python
import requests

# API configuration
API_BASE_URL = "http://localhost:8080/api/v1"
API_KEY = "admin"  # Default API key

# Call API with authentication
def call_api(method, endpoint, data=None):
    headers = {"Authorization": f"ApiKey {API_KEY}"}
    url = f"{API_BASE_URL}/{endpoint}"
    
    if method.upper() == "GET":
        response = requests.get(url, headers=headers)
    elif method.upper() == "POST":
        response = requests.post(url, json=data, headers=headers)
        
    return response.json()

# Start a session
result = call_api("POST", "session/start")
print(f"Session started: {result}")

# Create a project
project_data = {"path": "C:/Temp/TestProject.project"}
result = call_api("POST", "project/create", project_data)
print(f"Project created: {result}")
```

For a complete example workflow, see the [example_client.py](example_client.py) file.

## 🧰 Architecture

The CODESYS REST API consists of several key components:

1. **HTTP REST API Server**: Processes incoming requests and routes them to handlers
2. **CODESYS Session Manager**: Maintains and monitors the persistent CODESYS instance
3. **Script Execution Engine**: Generates and executes scripts in the CODESYS environment
4. **Authentication System**: Validates API keys and controls access

For more information about the architecture, see the [Project Summary](PROJECT_SUMMARY.md).

## 🔧 Configuration

### Server Configuration

Server settings can be configured by editing `HTTP_SERVER.py`:

```python
# Constants
SERVER_HOST = '0.0.0.0'  # Listen on all interfaces
SERVER_PORT = 8080       # HTTP port
CODESYS_PATH = r"C:\Program Files\CODESYS 3.5\CODESYS\CODESYS.exe"
```

### API Keys

API keys are stored in `api_keys.json`:

```json
{
  "admin": {"name": "Admin", "created": 1620000000.0}
}
```

## 📚 Documentation

- [Installation Guide](INSTALLATION_GUIDE.md): Detailed installation instructions
- [Implementation Checklist](IMPLEMENTATION_CHECKLIST.md): Development progress and status
- [Python 2.7 Compatibility](PY27_COMPATIBILITY.md): Notes on Python 2.7 compatibility
- [Project Summary](PROJECT_SUMMARY.md): Overview of implementation details

## 🚨 Troubleshooting

### Common Issues

- **API returns "Unauthorized"**: Check that you're using the correct API key
- **Service fails to start**: Verify CODESYS path is correct and CODESYS is installed
- **Connection refused**: Ensure the service is running and the port is not blocked

### Logs

Check the following log files for error messages:

- `codesys_api_server.log`: Main API server log
- `session.log`: CODESYS session log
- `codesys_api_service.log`: Windows service log (if running as a service)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- CODESYS Group for the CODESYS automation software and scripting API
- Python community for excellent libraries and tools
- All contributors to this project
