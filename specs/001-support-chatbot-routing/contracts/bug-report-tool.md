# Contract: `create_bug_report` Tool

Unchanged from the course starter (`setup_gateway.py`, `create_bug_report.py`). Documented here
because the prompt depends on it.

## As seen by the model

- Name: `bugreports___create_bug_report` (gateway target `bugreports` + `___` + tool name)
- Input schema (all required, all strings): `description`, `stepsToReproduce`, `environment`

## Lambda event (from the gateway; no envelope)

```json
{"description": "…", "stepsToReproduce": "…", "environment": "…"}
```

## Results returned to the model

| Case | Result |
|------|--------|
| Success | `{"ticketId": "<uuid4>", "status": "OPEN"}` and a DynamoDB item is written |
| Empty field(s) | `{"error": "missing required field(s): <names>. Ask the customer for them before filing the ticket."}` |
| Wrong tool name | `{"error": "unsupported tool: <name>"}` |

Prompt obligations: see [system-prompt.md](./system-prompt.md) B5–B7.
