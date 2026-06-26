# LLM API Inspect

LLM API Inspect is a small Dash + Plotly monitor for streaming first-token latency across LLM API providers.

It periodically sends this fixed prompt to each enabled target:

```text
ping. Reply with the single word: pong
```

The monitor records the time from request start to the first streamed text content, stores the result in SQLite, and renders recent latency as a heatmap.

## Features

- Configurable probe interval, dashboard window, request timeout, and color scale.
- SQLite persistence.
- Streaming first-token latency measurement.
- Dash + Plotly heatmap for recent status.
- Per-target enable/disable switch.
- Configurable colors for no data, failure, and latency thresholds.
- OpenAI-compatible, Anthropic-compatible, and Gemini streaming protocols.

## Project Layout

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

`page_demo.py` is the earlier standalone visual demo. Use `app.py` for the real monitor.

## Local Run

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the app:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8050
```

Optional runtime environment variables:

```text
INSPECT_HOST=0.0.0.0
INSPECT_PORT=8050
INSPECT_DEBUG=1
```

## Docker Run

Build the image:

```bash
docker build -t llm-api-inspect .
```

Run with a mounted config file:

```bash
docker run --rm -p 8050:8050 \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  -v inspect-data:/data \
  llm-api-inspect
```

For persistent SQLite data in Docker, set this in `config.yaml`:

```yaml
global:
  database_path: /data/inspect.db
```

On PowerShell, use:

```powershell
docker run --rm -p 8050:8050 `
  -v "${PWD}/config.yaml:/app/config.yaml:ro" `
  -v inspect-data:/data `
  llm-api-inspect
```

## Configuration

Edit `config.yaml`.

Global fields:

- `interval_minutes`: probe interval in minutes.
- `window_hours`: dashboard time window in hours.
- `timeout_ms`: request timeout in milliseconds.
- `database_path`: SQLite database path.

Color fields:

- `colors.no_data`: no-result cell color.
- `colors.failure`: failed-probe cell color.
- `colors.latency_scale`: latency-to-color stops.

Target fields:

- `title`: display title.
- `subtitle`: optional display subtitle.
- `base_url`: provider base URL without the API path.
- `api_key`: raw API key. Environment variable expansion is intentionally not supported.
- `protocol`: one of `openai_chat`, `openai_responses`, `anthropic_messages`, `gemini_generate`.
- `model`: model name.
- `enabled`: `true` or `false`.

Minimal target example:

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

## Protocols

- `openai_chat`: `POST /v1/chat/completions`
- `openai_responses`: `POST /v1/responses`
- `anthropic_messages`: `POST /v1/messages`
- `gemini_generate`: `POST /v1beta/models/{model}:streamGenerateContent?alt=sse`

Gemini uses `streamGenerateContent` because this project measures streaming first-token latency.

## Verification

Compile check:

```bash
python -m py_compile app.py inspect_core/config.py inspect_core/db.py inspect_core/time_utils.py inspect_core/probes.py inspect_core/scheduler.py
```

Dependency import check:

```bash
python -c "import dash, plotly, httpx, yaml; print('deps ok')"
```

## Security Notes

`config.yaml` may contain API keys. Do not commit or publish real keys, do not paste them into issue reports, and do not bake them into Docker images.
