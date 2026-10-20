# Contract: CLI Scripts (new and modified)

All scripts run from `project/starter/`, read `agentcore_config.json` by default
(`--config` to override), use region `us-east-1`, and exit non-zero on failure.

## `validate_offline.py` (new; standard library only; no AWS)

```
python validate_offline.py [--prompt-file system_prompt.txt] [--faq-file online_shop_faq.md]
                           [--tests-json harness-tests.json]
```

Prints one `PASS`/`FAIL` line per check (prompt S1–S6, test-suite schema and route counts, FAQ
entries 33–34). Exits 0 only if every check passes.
Importable functions: `check_prompt(text, faq) -> list[str]`, `check_tests(obj) -> list[str]`,
`check_faq(text) -> list[str]` (each returns a list of error messages).

## `guardrail.py` (new module)

- `load_guardrail(config: dict) -> tuple[str, str] | None`: returns `(guardrail_id, version)`
  from the config, or `None` if absent.
- `check_input(client, guardrail_id, version, text) -> GuardrailResult`: calls
  `bedrock-runtime.apply_guardrail(source="INPUT", content=[{"text": {"text": text}}])`.
  `GuardrailResult(blocked: bool, message: str | None, raw: dict)`. `blocked` is `True` iff
  `action == "GUARDRAIL_INTERVENED"`, and `message` is the first `outputs[].text`.
- Errors are raised as-is; callers fail closed (they don't invoke the harness and they print
  the error).

## `setup_guardrail.py` (new)

```
python setup_guardrail.py [--stack-name bug-report-guardrail-stack]
```

Reads the stack outputs `GuardrailId` and `GuardrailVersion` and merges `guardrail_id` and
`guardrail_version` into `agentcore_config.json`.

## `chat.py` / `generate-eval-dataset.py` (modified: opt-in)

New flag `--guardrail`. Without it, behavior is identical to the course version. With it:

- if the config has no guardrail, exit with a message to run `setup_guardrail.py`;
- each user message is checked first. When blocked, `chat.py` prints `[guardrail blocked]`
  followed by the message and skips the harness; `generate-eval-dataset.py` writes the blocked
  message as `response`.

## `multiturn_bug_test.py` (new)

```
python multiturn_bug_test.py [--guardrail] [--transcript-out ../evidence/transcripts/multiturn_bug.txt]
```

Runs a scripted conversation (built into the script) in one session, prints the transcript,
extracts the ticket UUID from the final reply, reads the item from `table_name`, and asserts
that each field contains the scripted keywords. It also asserts that no tool call happened
before the final turn. Exit 0 means pass.
Importable helpers: `extract_ticket_id(text) -> str | None`,
`field_matches(value, keywords) -> bool`.

## `run_bedrock_eval.py` (new)

```
python run_bedrock_eval.py [--dataset output_eval_dataset.jsonl] [--job-name support-chatbot-eval-run-<UTC timestamp>]
                           [--stack-name bug-report-testing-stack] [--wait] [--scores-out ../evidence/eval_scores.md]
```

Uploads the dataset, creates the job (`Builtin.Correctness`, evaluator `amazon.nova-pro-v1:0`,
`precomputedInferenceSource.inferenceSourceIdentifier = my-support-chatbot`), and prints the
job ARN. With `--wait`, it polls until the job reaches a terminal status, downloads the result
JSONL files under the output prefix, and prints and writes a per-record table
(`# | prompt (truncated) | score`) plus the mean.

## `mask_evidence.py` (new)

```
python mask_evidence.py [--out-dir ../evidence]
```

Copies `agentcore_config.json` and `output_eval_dataset.jsonl` (if they exist) into `--out-dir`,
replacing every 12-digit AWS account ID with `************`.
