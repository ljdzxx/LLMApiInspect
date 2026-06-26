# Repository Guidelines

## Project Overview

This repository contains `LLM API Inspect`, a Dash + Plotly web monitor for streaming first-token latency across LLM API providers.

The application:

- Reads runtime settings from `config.yaml`.
- Sends periodic streaming probes to enabled targets.
- Stores probe results in SQLite.
- Displays recent latency as a configurable heatmap.

## Structure

- `app.py`: Dash application entry point and dashboard rendering.
- `config.yaml`: Local runtime configuration. It may contain API keys and must be treated as sensitive.
- `requirements.txt`: Python dependencies.
- `inspect_core/config.py`: Configuration parsing and validation.
- `inspect_core/db.py`: SQLite schema, inserts, and queries.
- `inspect_core/probes.py`: Provider-specific streaming probe logic.
- `inspect_core/scheduler.py`: Background probe scheduler.
- `inspect_core/time_utils.py`: Time and bucket helpers.
- `page_demo.py`: Earlier standalone demo, not the production entry point.

## Development Commands

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run locally:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:8050
```

Compile check:

```bash
python -m py_compile app.py inspect_core/config.py inspect_core/db.py inspect_core/time_utils.py inspect_core/probes.py inspect_core/scheduler.py
```

## Configuration Rules

- Do not add environment-variable API key expansion. The current product decision is explicit raw `api_key` values in `config.yaml`.
- Do not log API keys.
- Do not store API keys in SQLite.
- Do not include real API keys in documentation, examples, tests, or Docker image layers.
- Keep disabled targets out of the heatmap.
- Keep color thresholds configurable through `colors.latency_scale`, `colors.failure`, and `colors.no_data`.

## Provider Protocols

Supported `protocol` values:

- `openai_chat`: OpenAI-compatible `POST /v1/chat/completions`.
- `openai_responses`: OpenAI-compatible `POST /v1/responses`.
- `anthropic_messages`: Anthropic-compatible `POST /v1/messages`.
- `gemini_generate`: Gemini streaming `POST /v1beta/models/{model}:streamGenerateContent?alt=sse`.

The project measures first streamed text content, not full response completion time.

## Change Guidelines

- Prefer small, direct changes over broad refactors.
- Preserve the single-process architecture unless the task explicitly asks for a queue, worker service, or separate API server.
- Keep SQLite writes simple and short-lived.
- Use standard library facilities before adding dependencies.
- If changing probe parsing, preserve provider-specific behavior and add a local parsing check where practical.
- If changing dashboard behavior, verify empty data, failed probes, and successful probes still render.

## Docker Notes

The Docker image must not bake in `config.yaml`, because that file can contain API keys. Mount it at runtime instead.
