<div align="right"><a href="#简体中文">简体中文</a> | <a href="#english">English</a></div>

<a id="简体中文"></a>

# Hermes-飞书-A2A

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=22&duration=2800&pause=900&color=22C55E&center=true&vCenter=true&repeat=true&width=720&lines=%E6%9C%89%E8%BE%B9%E7%95%8C%E7%9A%84%E5%B7%A5%E4%BD%9C%E6%B5%81%E8%BE%93%E5%85%A5%EF%BC%8C%E5%8F%AF%E8%BF%BD%E6%BA%AF%E7%9A%84%E7%BB%93%E6%9E%9C%E8%BE%93%E5%87%BA%E3%80%82;%E8%AE%A1%E5%88%92+%E2%86%92+%E5%88%86%E6%B4%BE+%E2%86%92+%E9%AA%8C%E8%AF%81+%E2%86%92+%E4%BA%A4%E4%BB%98%E3%80%82;%E5%9C%A8%E9%A3%9E%E4%B9%A6%2FLark+%E5%86%85%E5%AE%89%E5%85%A8%E5%8D%8F%E8%B0%83+Agent%E3%80%82" alt="动态项目摘要：有边界的工作流、可追溯的结果和安全的 Agent 协调" />
</p>

一个自托管的工作流协调器，通过 HTTP 或飞书/Lark 将边界明确的任务分派给已注册的 Agent。

[![CI](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-F4C430.svg)](LICENSE)

Hermes 存储 Agent 身份与工作流状态、执行依赖屏障、分派就绪任务、应用超时与重试，并通过经过身份验证的 API 提供运行结果。飞书 webhook 事件会根据已配置的签名、会话白名单和发送者白名单进行验证。

Hermes 不包含 LLM 规划器或 Agent 运行时。调用方必须提交工作流定义，而每个 Agent 都必须提供 HTTP 适配器或飞书适配器，将结果返回 Hermes。飞书文件接收是一个确定性的例外：配置后，获得授权的文件消息会被路由到一个已注册的接收 Agent。

## 目录

- [支持的平台](#支持的平台)
- [架构](#架构)
- [快速开始](#zh-quick-start)
- [Docker](#docker-1)
- [Agent 契约](#agent-契约)
- [运行工作流](#运行工作流)
- [飞书配置](#飞书配置)
- [API 参考](#api-参考)
- [生产部署](#生产部署)
- [开发](#开发)

## 支持的平台

| 平台 | 原生安装 | 容器安装 | 持续验证 |
| --- | --- | --- | --- |
| macOS | Python 3.11 或更高版本 | Docker Desktop | `macos-latest` |
| Windows | Python 3.11 或更高版本 | 使用 Linux 容器的 Docker Desktop | `windows-latest` |
| Linux | Python 3.11 或更高版本 | Docker Engine 与 Compose v2 | `ubuntu-latest` |

Python wheel 与平台无关。发布的容器支持 `linux/amd64` 和 `linux/arm64`。

## 架构

![Hermes 飞书 A2A 架构](docs/assets/readme-architecture.svg)

<a id="zh-quick-start"></a>

## 快速开始

### 1. 安装

前置条件：Git 和 Python 3.11 或更高版本。

macOS 或 Linux：

```bash
git clone https://github.com/ChrysFu-FndVent/hermes-feishu-a2a.git
cd hermes-feishu-a2a
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
```

Windows PowerShell：

```powershell
git clone https://github.com/ChrysFu-FndVent/hermes-feishu-a2a.git
Set-Location hermes-feishu-a2a
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install .
```

这些命令不要求激活 shell，因此在 PowerShell 脚本执行受限时也能使用。

### 2. 配置

macOS 或 Linux：

```bash
cp .env.example .env
cp config/agents.example.yaml config/agents.yaml
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
Copy-Item config\agents.example.yaml config\agents.yaml
```

编辑两个文件并替换所有占位符。生产环境必需的设置包括：

| 变量 | 用途 |
| --- | --- |
| `HERMES_INTERNAL_API_TOKEN` | 保护 API 的至少 32 字符随机值 |
| `HERMES_FEISHU_APP_ID` | 飞书/Lark 自建应用 ID |
| `HERMES_FEISHU_APP_SECRET` | 自建应用密钥 |
| `HERMES_FEISHU_ENCRYPT_KEY` | 用于签名的事件订阅加密密钥 |
| `HERMES_FEISHU_VERIFICATION_TOKEN` | 事件订阅验证令牌 |
| `HERMES_FEISHU_ALLOWED_CHAT_IDS` | 以逗号分隔的 `oc_...` 会话 ID |
| `HERMES_FEISHU_OWNER_OPEN_IDS` | 以逗号分隔的 `ou_...` 人类所有者 ID |
| `HERMES_FEISHU_FILE_INTAKE_AGENT_ID` | 处理获授权飞书文件消息的已注册 Agent |
| `HERMES_AGENTS_CONFIG_PATH` | Agent 注册表文件，通常为 `config/agents.yaml` |

`HERMES_PORT` 控制原生 Python 启动端口。`HERMES_PUBLISHED_PORT` 控制 Docker Compose 使用的主机端口；容器始终监听 8080 端口。

在本地生成内部 API 令牌：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

在 Windows 上使用 `py -3.11` 代替 `python3`。

每个 HTTP Agent 都需要 `endpoint`。每个飞书 Agent 都需要 `open_id` 和 `metadata.chat_id`。无效的 Agent 记录会使验证和启动停止，而不是在第一次分派时才失败。

验证完整配置：

macOS 或 Linux：

```bash
.venv/bin/hermes-a2a validate-config --path config/agents.yaml
```

Windows PowerShell：

```powershell
.venv\Scripts\hermes-a2a.exe validate-config --path config\agents.yaml
```

### 3. 运行

macOS 或 Linux：

```bash
.venv/bin/hermes-a2a serve
```

Windows PowerShell：

```powershell
.venv\Scripts\hermes-a2a.exe serve
```

启动后打开以下 URL：

- `http://127.0.0.1:8080/healthz`：进程健康状态。
- `http://127.0.0.1:8080/readyz`：生产配置就绪状态。
- `http://127.0.0.1:8080/docs`：交互式 API。

在生产模式下，只有当所有必需的飞书配置和白名单都是真实且非占位值时，`/readyz` 才不会返回 HTTP 503。

## Docker

Docker 使用上面创建的相同 `.env` 和 `config/agents.yaml` 文件。

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f hermes
```

Compose 文件使用命名卷存储 SQLite 数据。这可以避免 Linux 上的主机目录所有权问题，也适用于 macOS 和 Windows 上的 Docker Desktop。

停止服务但不删除数据：

```bash
docker compose down
```

只有在明确要删除所有 Agent、工作流和运行记录时，才删除命名数据卷：

```bash
docker compose down --volumes
```

## Agent 契约

Agent 从 `config/agents.yaml` 预加载，初始状态为 `offline`。适配器必须先发送心跳，Hermes 才会向其分派工作。

```json
{
  "status": "online",
  "capabilities": ["review", "testing"]
}
```

携带 `X-Hermes-Token` 请求头，将此负载发送到 `POST /agents/{agent_id}/heartbeat`。

### HTTP Agent

Hermes 向已配置的端点发送 HTTP `POST` 请求：

```json
{
  "run_id": "run-123",
  "task": {
    "id": "review",
    "title": "Review",
    "prompt": "Check the result",
    "agent_id": "reviewer"
  },
  "attachments": []
}
```

当任务包含飞书附件引用时，Hermes 会在分派时下载并解析附件。顶层 `attachments` 数组随后包含 `name`、`media_type`、`text` 和原始安全引用。文件字节和飞书凭据绝不会发送给 Agent。

端点必须返回包含 `output` 或 `message` 的 JSON。

```json
{"output": "Review completed"}
```

### 飞书 Agent

Hermes 向已配置的 `open_id` 发送原生 `at` 帖子，并等待 Agent 在该任务消息线程中回复，或调用 `POST /events/agent-result`。线程回复会与任务消息和已注册 Agent 的 `open_id` 匹配。API 回调必须包含相同的 `run_id`、`task_id` 和已分配的 `agent_id`。

对于带附件的任务，原生帖子会在任务提示后附上有边界的提取文本。较大内容会在 `HERMES_FEISHU_FILE_MAX_AGENT_CHARS` 处截断。

```json
{
  "run_id": "run-123",
  "task_id": "review",
  "agent_id": "reviewer",
  "success": true,
  "output": "Review completed"
}
```

如果在任务超时前既未收到匹配的线程回复，也未收到回调，Hermes 会使用已配置的重试预算，并最终将任务标记为失败。

## 运行工作流

1. 使用 `GET /agents` 确认目标 Agent 为 `online`。
2. 将 JSON 工作流定义提交到 `POST /workflows`。
3. 使用 `POST /workflows/{workflow_id}/run` 启动工作流。
4. 轮询 `GET /runs/{run_id}`，直到运行状态为 `succeeded` 或 `failed`。

四个端点都需要 `X-Hermes-Token`。`/docs` 的交互式 API 是在 macOS、Windows 和 Linux 上执行首次运行最便携的方式。[`examples/`](examples/) 中提供了工作流定义示例。

![任务生命周期](docs/assets/task-lifecycle.svg)

## 飞书配置

1. 创建飞书/Lark 自建应用并启用机器人功能。
2. 授予租户所需的消息接收/发送和会话读取权限。
3. 对直接附加到消息的文件授予 `im:resource`。
4. 对共享的 `/file/...` 云空间链接授予应用身份权限 `drive:file:download`。更宽泛的 `drive:drive:readonly` 权限也可用，但并非必需。
5. 订阅 `im.message.receive_v1`。
6. 将 HTTPS 回调设置为 `https://your-host.example/webhooks/feishu`。
7. 将应用 ID、应用密钥、加密密钥和验证令牌复制到 `.env`。
8. 将明确的会话 ID 和所有者 open ID 加入白名单。
9. 发布应用版本、取得租户审批，并将机器人加入目标会话。

Webhook 在解析 JSON 前对原始请求体进行身份验证，然后检查验证令牌、会话 ID 和发送者身份。已接受的消息是集成事件；本服务不会自动把自然语言转换成工作流。如需这种行为，请使用外部规划器或适配器调用工作流 API。

### 文件接收

将 `HERMES_FEISHU_FILE_INTAKE_AGENT_ID` 设置为 `config/agents.yaml` 中的 HTTP 或飞书 Agent，为其授予 `attachment:read`，并确保它发送 `online` 心跳。当白名单内的人类发布受支持的附件或 `/file/...` 链接时，Hermes 会：

1. 提取消息资源 key 或 Drive 文件 token；
2. 使用应用的 tenant token 下载文件；
3. 执行已配置的文件数量、压缩/解压字节数、类型和文本限制；
4. 从 PDF、DOCX、TXT、Markdown、CSV 或 JSON 中提取文本；
5. 在接收 Agent 上启动一个工作流；
6. 在原飞书消息中回复 Agent 结果。

事件会按事件/消息 ID 认领，因此飞书重试不会创建重复运行。已注册 Agent 或其他应用发送的消息绝不会触发文件接收，从而防止机器人回复循环。纯图片或扫描 PDF 需要外部 OCR 适配器；Hermes 会拒绝不含可提取文本的 PDF。

详细权限与回调清单见[飞书权限和事件配置](docs/feishu-permissions.md)。

![安全模型](docs/assets/security-model.svg)

## API 参考

| 端点 | 身份验证 | 用途 |
| --- | --- | --- |
| `GET /healthz` | 网络限制 | 进程健康状态 |
| `GET /readyz` | 网络限制 | 生产配置就绪状态 |
| `GET /metrics` | 网络限制 | Agent 和工作流计数器 |
| `GET/POST /agents` | `X-Hermes-Token` | 列出或注册 Agent |
| `POST /agents/{id}/heartbeat` | `X-Hermes-Token` | 更新 Agent 健康状态 |
| `POST /workflows` | `X-Hermes-Token` | 存储工作流定义 |
| `POST /workflows/{id}/run` | `X-Hermes-Token` | 启动执行 |
| `GET /runs/{run_id}` | `X-Hermes-Token` | 检查任务状态和结果 |
| `POST /events/agent-result` | `X-Hermes-Token` | 完成异步 Agent 任务 |
| `POST /webhooks/feishu` | 飞书签名和令牌 | 接收飞书事件 |

## 生产部署

- 在反向代理或托管负载均衡器终止 TLS。
- 只公开 `/webhooks/feishu`。
- 除使用内部令牌外，还要将内部 API 保持在私有网络中。
- 固定发布标签或容器摘要，不要直接部署 `main`。
- 升级前备份 SQLite 数据卷。

发布资产包括与平台无关的 wheel 和源代码归档。发布的容器标签支持 `linux/amd64` 和 `linux/arm64`：

```bash
docker pull ghcr.io/chrysfu-fndvent/hermes-feishu-a2a:latest
```

运行细节见[部署](docs/deployment.md)、[最佳实践](docs/best-practices.md)和[故障排除](docs/troubleshooting.md)。

## 开发

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy src
pytest -q
python scripts/check_secrets.py
python -m build
```

参见 [CONTRIBUTING.md](CONTRIBUTING.md)。本项目以 [MIT License](LICENSE) 发布。

<a id="english"></a>

# Hermes Feishu A2A

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=22&duration=2800&pause=900&color=22C55E&center=true&vCenter=true&repeat=true&width=720&lines=Bounded+workflows+in.+Traceable+results+out.;Plan+%E2%86%92+Dispatch+%E2%86%92+Verify+%E2%86%92+Deliver.;Secure+agent+coordination+inside+Feishu%2FLark." alt="Animated project summary: bounded workflows, traceable results, and secure agent coordination" />
</p>

A self-hosted workflow coordinator for dispatching bounded tasks to registered
Agents through HTTP or Feishu/Lark.

[![CI](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ChrysFu-FndVent/hermes-feishu-a2a/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-F4C430.svg)](LICENSE)

Hermes stores Agent identities and workflow state, enforces dependency barriers,
dispatches ready tasks, applies timeouts and retries, and exposes run results through
an authenticated API. Feishu webhook events are verified against the configured
signature, chat and sender allow-lists.

Hermes does not include an LLM planner or an Agent runtime. A caller must submit a
workflow definition, and every Agent must expose either an HTTP adapter or a Feishu
adapter that returns results to Hermes. Feishu file intake is a deterministic exception:
when configured, authorized file messages are routed to one registered intake Agent.

## Table of contents

- [Supported platforms](#supported-platforms)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Docker](#docker)
- [Agent contract](#agent-contract)
- [Run a workflow](#run-a-workflow)
- [Feishu setup](#feishu-setup)
- [API reference](#api-reference)
- [Production deployment](#production-deployment)
- [Development](#development)

## Supported platforms

| Platform | Native installation | Container installation | Continuous validation |
| --- | --- | --- | --- |
| macOS | Python 3.11 or newer | Docker Desktop | `macos-latest` |
| Windows | Python 3.11 or newer | Docker Desktop with Linux containers | `windows-latest` |
| Linux | Python 3.11 or newer | Docker Engine and Compose v2 | `ubuntu-latest` |

The Python wheel is platform-independent. The published container supports
`linux/amd64` and `linux/arm64`.

## Architecture

![Hermes Feishu A2A architecture](docs/assets/readme-architecture.svg)

## Quick start

### 1. Install

Prerequisites: Git and Python 3.11 or newer.

macOS or Linux:

```bash
git clone https://github.com/ChrysFu-FndVent/hermes-feishu-a2a.git
cd hermes-feishu-a2a
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install .
```

Windows PowerShell:

```powershell
git clone https://github.com/ChrysFu-FndVent/hermes-feishu-a2a.git
Set-Location hermes-feishu-a2a
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install .
```

These commands do not require shell activation, so they also work when PowerShell
script execution is restricted.

### 2. Configure

macOS or Linux:

```bash
cp .env.example .env
cp config/agents.example.yaml config/agents.yaml
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
Copy-Item config\agents.example.yaml config\agents.yaml
```

Edit both files and replace every placeholder. The required production settings are:

| Variable | Purpose |
| --- | --- |
| `HERMES_INTERNAL_API_TOKEN` | Random value of at least 32 characters for protected APIs |
| `HERMES_FEISHU_APP_ID` | Feishu/Lark custom app ID |
| `HERMES_FEISHU_APP_SECRET` | Custom app secret |
| `HERMES_FEISHU_ENCRYPT_KEY` | Event subscription encrypt key used for signatures |
| `HERMES_FEISHU_VERIFICATION_TOKEN` | Event subscription verification token |
| `HERMES_FEISHU_ALLOWED_CHAT_IDS` | Comma-separated `oc_...` chat IDs |
| `HERMES_FEISHU_OWNER_OPEN_IDS` | Comma-separated `ou_...` human owner IDs |
| `HERMES_FEISHU_FILE_INTAKE_AGENT_ID` | Registered Agent that processes authorized Feishu file messages |
| `HERMES_AGENTS_CONFIG_PATH` | Agent registry file, normally `config/agents.yaml` |

`HERMES_PORT` controls native Python startup. `HERMES_PUBLISHED_PORT` controls the
host port used by Docker Compose; the container always listens on port 8080.

Generate the internal API token locally:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

On Windows, use `py -3.11` instead of `python3`.

Each HTTP Agent needs an `endpoint`. Each Feishu Agent needs an `open_id` and
`metadata.chat_id`. Invalid Agent records stop validation and startup instead of
failing during the first dispatch.

Validate the complete configuration:

macOS or Linux:

```bash
.venv/bin/hermes-a2a validate-config --path config/agents.yaml
```

Windows PowerShell:

```powershell
.venv\Scripts\hermes-a2a.exe validate-config --path config\agents.yaml
```

### 3. Run

macOS or Linux:

```bash
.venv/bin/hermes-a2a serve
```

Windows PowerShell:

```powershell
.venv\Scripts\hermes-a2a.exe serve
```

Open these URLs after startup:

- `http://127.0.0.1:8080/healthz` for process health.
- `http://127.0.0.1:8080/readyz` for production configuration readiness.
- `http://127.0.0.1:8080/docs` for the interactive API.

`/readyz` returns HTTP 503 in production until all required Feishu values and
allow-lists are real, non-placeholder values.

## Docker

Docker uses the same `.env` and `config/agents.yaml` files created above.

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f hermes
```

The Compose file uses a named volume for SQLite data. This avoids host directory
ownership problems on Linux and works with Docker Desktop on macOS and Windows.

Stop the service without deleting data:

```bash
docker compose down
```

Delete the named data volume only when you intentionally want to erase all Agent,
workflow and run records:

```bash
docker compose down --volumes
```

## Agent contract

Agents are preloaded from `config/agents.yaml` with `offline` status. An adapter must
send a heartbeat before Hermes dispatches work to it.

```json
{
  "status": "online",
  "capabilities": ["review", "testing"]
}
```

Send this payload to `POST /agents/{agent_id}/heartbeat` with the
`X-Hermes-Token` header.

### HTTP Agents

Hermes sends an HTTP `POST` request to the configured endpoint:

```json
{
  "run_id": "run-123",
  "task": {
    "id": "review",
    "title": "Review",
    "prompt": "Check the result",
    "agent_id": "reviewer"
  },
  "attachments": []
}
```

When a task contains Feishu attachment references, Hermes downloads and parses them
at dispatch time. The top-level `attachments` array then contains `name`, `media_type`,
`text`, and the original safe reference. File bytes and Feishu credentials are never
sent to the Agent.

The endpoint must return JSON containing `output` or `message`.

```json
{"output": "Review completed"}
```

### Feishu Agents

Hermes sends a native `at` post to the configured `open_id` and waits for the Agent
to reply in that task message thread or call `POST /events/agent-result`. Thread replies
are matched to the task message and registered Agent `open_id`. API callbacks must
include the same `run_id`, `task_id` and assigned `agent_id`.

For tasks with attachments, the native post includes the bounded extracted text after
the task prompt. Large content is truncated at `HERMES_FEISHU_FILE_MAX_AGENT_CHARS`.

```json
{
  "run_id": "run-123",
  "task_id": "review",
  "agent_id": "reviewer",
  "success": true,
  "output": "Review completed"
}
```

If neither a matching thread reply nor callback arrives before the task timeout, Hermes
applies the configured retry budget and eventually marks the task failed.

## Run a workflow

1. Confirm the target Agents are `online` with `GET /agents`.
2. Submit a JSON workflow definition to `POST /workflows`.
3. Start it with `POST /workflows/{workflow_id}/run`.
4. Poll `GET /runs/{run_id}` until the run is `succeeded` or `failed`.

All four endpoints require `X-Hermes-Token`. The interactive API at `/docs` is the
most portable way to perform the first run on macOS, Windows and Linux. Example
workflow definitions are available in [`examples/`](examples/).

![Task lifecycle](docs/assets/task-lifecycle.svg)

## Feishu setup

1. Create a Feishu/Lark custom app and enable bot functionality.
2. Grant message receive/send and chat read permissions required by your tenant.
3. Grant `im:resource` for files attached directly to messages.
4. Grant the application-identity scope `drive:file:download` for shared
   `/file/...` cloud-space links. The broader `drive:drive:readonly` scope also
   works, but is not required.
5. Subscribe to `im.message.receive_v1`.
6. Set the HTTPS callback to `https://your-host.example/webhooks/feishu`.
7. Copy the app ID, app secret, encrypt key and verification token into `.env`.
8. Add explicit chat and owner open IDs to the allow-lists.
9. Publish the app version, obtain tenant approval, and add the bot to the target chat.

The webhook authenticates the raw request body before JSON parsing, then checks the
verification token, chat ID and sender identity. An accepted message is an integration
event; this service does not automatically translate natural language into a workflow.
Use an external planner or adapter to call the workflow API when that behavior is needed.

### File intake

Set `HERMES_FEISHU_FILE_INTAKE_AGENT_ID` to an HTTP or Feishu Agent from
`config/agents.yaml`, grant that Agent `attachment:read`, then make sure it sends an
`online` heartbeat. When an allow-listed human posts a supported attachment or a
`/file/...` link, Hermes:

1. extracts the message resource key or Drive file token;
2. downloads the file with the app's tenant token;
3. enforces the configured file-count, compressed/uncompressed byte, type and text limits;
4. extracts text from PDF, DOCX, TXT, Markdown, CSV or JSON;
5. starts one workflow on the intake Agent; and
6. replies to the original Feishu message with the Agent result.

Events are claimed by event/message ID so Feishu retries do not create duplicate runs.
Messages sent by registered Agents or other apps never trigger file intake, preventing
bot reply loops. Image-only or scanned PDFs require an external OCR adapter; Hermes
rejects PDFs that contain no extractable text.

See [Feishu permissions and event setup](docs/feishu-permissions.md) for the detailed
scope and callback checklist.

![Security model](docs/assets/security-model.svg)

## API reference

| Endpoint | Authentication | Purpose |
| --- | --- | --- |
| `GET /healthz` | Network restriction | Process health |
| `GET /readyz` | Network restriction | Production configuration readiness |
| `GET /metrics` | Network restriction | Agent and workflow counters |
| `GET/POST /agents` | `X-Hermes-Token` | List or register Agents |
| `POST /agents/{id}/heartbeat` | `X-Hermes-Token` | Update Agent health |
| `POST /workflows` | `X-Hermes-Token` | Store a workflow definition |
| `POST /workflows/{id}/run` | `X-Hermes-Token` | Start execution |
| `GET /runs/{run_id}` | `X-Hermes-Token` | Inspect task states and results |
| `POST /events/agent-result` | `X-Hermes-Token` | Complete an asynchronous Agent task |
| `POST /webhooks/feishu` | Feishu signature and token | Receive Feishu events |

## Production deployment

- Terminate TLS at a reverse proxy or managed load balancer.
- Expose only `/webhooks/feishu` publicly.
- Keep internal APIs on a private network in addition to using the internal token.
- Pin a release tag or container digest instead of deploying `main` directly.
- Back up the SQLite volume before upgrades.

Published release assets include a platform-independent wheel and source archive.
Published container tags support `linux/amd64` and `linux/arm64`:

```bash
docker pull ghcr.io/chrysfu-fndvent/hermes-feishu-a2a:latest
```

See [deployment](docs/deployment.md), [best practices](docs/best-practices.md), and
[troubleshooting](docs/troubleshooting.md) for operational details.

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
mypy src
pytest -q
python scripts/check_secrets.py
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md). This project is released under the
[MIT License](LICENSE).

---

<p align="right"><a href="#english">Back to English</a></p>

---
