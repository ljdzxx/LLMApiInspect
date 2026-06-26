# LLM API Inspect

LLM API Inspect 是一个基于 Dash + Plotly 的 LLM API 流式首字延迟监控工具。

它会按配置周期向每个已启用的监控对象发送固定提示词：

```text
ping. Reply with the single word: pong
```

系统记录从请求开始到收到第一个流式文本内容之间的耗时，将结果写入 SQLite，并在前端用热力图展示最近一段时间的延迟状态。

## 功能

- 可配置监控间隔、展示窗口、请求超时时间和颜色阈值。
- 使用 SQLite 持久化监控结果。
- 统计流式响应的首字延迟，而不是完整响应耗时。
- 使用 Dash + Plotly 展示最近状态热力图。
- 支持按监控对象启用或禁用。
- 支持配置无数据、失败、不同延迟区间的颜色。
- 支持 OpenAI 兼容协议、Anthropic 兼容协议和 Gemini 流式协议。

## 项目结构

```text
.
|-- app.py
|-- config.yaml
|-- requirements.txt
|-- Dockerfile
|-- inspect_core/
|   |-- config.py
|   |-- db.py
|   |-- probes.py
|   |-- scheduler.py
|   `-- time_utils.py
`-- page_demo.py
```

`page_demo.py` 是早期的独立可视化演示文件。真实监控服务请使用 `app.py`。

## 本地运行

安装依赖：

```bash
python -m pip install -r requirements.txt
```

启动应用：

```bash
python app.py
```

打开：

```text
http://127.0.0.1:8050
```

可选运行环境变量：

```text
INSPECT_HOST=0.0.0.0
INSPECT_PORT=8050
INSPECT_DEBUG=1
```

## Docker 运行

构建镜像：

```bash
docker build -t llm-api-inspect .
```

通过挂载配置文件运行：

```bash
docker run --rm -p 8050:8050 \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  -v inspect-data:/data \
  llm-api-inspect
```

如果希望 Docker 中的 SQLite 数据持久化，建议在 `config.yaml` 中这样配置：

```yaml
global:
  database_path: /data/inspect.db
```

PowerShell 示例：

```powershell
docker run --rm -p 8050:8050 `
  -v "${PWD}/config.yaml:/app/config.yaml:ro" `
  -v inspect-data:/data `
  llm-api-inspect
```

## 配置说明

编辑 `config.yaml`。

全局配置：

- `interval_minutes`：监控间隔，单位为分钟。
- `window_hours`：前端热力图展示窗口，单位为小时。
- `timeout_ms`：请求超时时间，单位为毫秒。
- `database_path`：SQLite 数据库路径。

颜色配置：

- `colors.no_data`：无数据格子的颜色。
- `colors.failure`：请求失败格子的颜色。
- `colors.latency_scale`：延迟数值到颜色的映射阈值。

监控对象配置：

- `title`：监控对象标题。
- `subtitle`：监控对象副标题，可选。
- `base_url`：服务商基础地址，不包含具体 API 路径。
- `api_key`：原始 API Key。当前不支持环境变量展开。
- `protocol`：协议类型，可选 `openai_chat`、`openai_responses`、`anthropic_messages`、`gemini_generate`。
- `model`：模型名称。
- `enabled`：是否启用，取值为 `true` 或 `false`。

最小监控对象示例：

```yaml
targets:
  - title: OpenAI Example
    subtitle: gpt-4.1-mini
    base_url: https://api.openai.com
    api_key: sk-replace-me
    protocol: openai_chat
    model: gpt-4.1-mini
    enabled: true
```

## 协议

- `openai_chat`：`POST /v1/chat/completions`
- `openai_responses`：`POST /v1/responses`
- `anthropic_messages`：`POST /v1/messages`
- `gemini_generate`：`POST /v1beta/models/{model}:streamGenerateContent?alt=sse`

Gemini 使用 `streamGenerateContent`，因为本项目需要测量流式首字延迟。

## 验证

编译检查：

```bash
python -m py_compile app.py inspect_core/config.py inspect_core/db.py inspect_core/time_utils.py inspect_core/probes.py inspect_core/scheduler.py
```

依赖导入检查：

```bash
python -c "import dash, plotly, httpx, yaml; print('deps ok')"
```

## 安全说明

`config.yaml` 可能包含 API Key。不要提交或公开真实密钥，不要把密钥粘贴到 issue、日志或文档中，也不要把它们打包进 Docker 镜像。
