# Evolutionary-SDE

Cursor-integrated **layered interviewer**: evolve a coding solution through algorithmic critique, Unicode and correctness stress, 10M+ / memory-bound scale, and async / event-driven architecture (Kafka, SQS, Redis, etc.).

## Cursor behavior

- **`.cursorrules`** (root): full “bar raiser” personality and engineering checklist.
- **`.cursor/rules/evolutionary-sde.mdc`**: `alwaysApply` pointer so Cursor picks it up in-rule UI.

## Backend (FastAPI + LangGraph)

Use **Python 3.11+** (3.11–3.12 recommended; some LangChain dependencies warn on pre-release Python versions).

Install:

```bash
cd /path/to/Evolutionary-SDE
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# Optional LLM scoring:
pip install -e ".[openai]"
```

Run API (default `http://127.0.0.1:8765`):

```bash
python -m evolutionary_sde.api.main
# or
evolutionary-sde-api
```

Data directory: `data/` (override with `EVOLUTIONARY_SDE_DATA`).

### Endpoints

| Method | Path | Purpose |
|--------|------|--------|
| `POST` | `/sessions` | Start a session with `problem_statement` |
| `GET` | `/sessions/{id}` | Session state |
| `POST` | `/sessions/{id}/code` | Submit code (optional auto draft if code changed) |
| `POST` | `/sessions/{id}/advance` | Run the next LangGraph layer (`Assess` → … → `System_Design`) |
| `POST` | `/drafts` | Log before/after code + rationale (decision log) |
| `GET` | `/sessions/{id}/decision-log` | Session + drafts + timeline |
| `POST` | `/analyze/cost-benefit` | Founder-style score (heuristic; set `OPENAI_API_KEY` for LLM) |

### Cost-benefit JSON body (example)

```json
{
  "design_summary": "Kafka for job pipeline; workers idempotent; DLQ for poison pills.",
  "primary_choice": "kafka",
  "alternatives": ["sqs", "rabbitmq"],
  "workload_hints": { "record_count": 100000000, "regions": ["us-east-1"] }
}
```

## LangGraph graph

Nodes: **assess** → **inject_chaos** → **scale_up** → **system_design** → `END`. The API advances **one node per** `POST .../advance` via `run_interviewer_step`, so you can edit code between layers.

## License

Add your preferred license.
