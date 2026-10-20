# Implementation Plan: Customer Support Chatbot Routing

**Branch**: `001-support-chatbot-routing` | **Date**: 2026-10-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-support-chatbot-routing/spec.md`

## Summary

Build the chatbot's behavior as a single, sectioned system prompt
(`project/starter/system_prompt.txt`) that routes each message to exactly one of three routes:

- **Bug report**: multi-turn collection, then the `bugreports___create_bug_report` tool.
- **Platform question**: answers only from the FAQ embedded through `{{FAQ}}`.
- **Other**: a polite hand-off to `+1 (800) 555-0199`.

The course infrastructure (CloudFormation, Lambda, gateway, harness, chat and dataset scripts)
is reused unchanged except for an opt-in `--guardrail` flag. Additive tooling provides:

- a Bedrock Guardrail applied client-side with `ApplyGuardrail` (research R1/R2);
- an offline validator with pytest and CI;
- a scripted multi-turn bug-report verifier;
- an evaluation-job helper;
- evidence masking;
- a 24-case test suite;
- a full README runbook.

## Technical Context

**Language/Version**: Python ≥ 3.9 (local 3.13; CI matrix 3.9 and 3.12); Lambda on `python3.12`
(unchanged)

**Primary Dependencies**: `boto3`/`botocore` 1.43.76 (pinned); `pytest` (dev only)

**Storage**: DynamoDB table `bug-report-tool-stack-bug-reports` (existing); S3 bucket
`udacity-agentic-engineer-c1-eval-<account>` (existing testing stack)

**Testing**: `pytest` + `botocore.stub.Stubber` (offline); `validate_offline.py` (offline gate);
`multiturn_bug_test.py` and `generate-eval-dataset.py` + Bedrock Evaluations (online, run by
the owner)

**Target Platform**: Amazon Bedrock AgentCore managed harness in `us-east-1`; model
`us.amazon.nova-pro-v1:0`; local CLI on macOS/Linux

**Project Type**: prompt-engineering project with CLI tooling and infrastructure as code

**Performance Goals**: a single chat turn completes within the client's 300 s read timeout;
typical turn ≤ 15 s with no tool call

**Constraints**: all behavior lives in the prompt (Constitution I); rendered prompt ≤ ~32k
characters; region `us-east-1`; no credentials in the repo; guardrail must not block
legitimate messages

**Scale/Scope**: 1 harness, 1 gateway, 1 tool, 1 guardrail; 24 single-turn tests and 1
scripted multi-turn conversation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Pre-design | Post-design |
|-----------|------|------------|-------------|
| I. Prompt is the product | Routing only in `system_prompt.txt`; course scripts functionally unchanged; tooling additive | ✅ | ✅ (one justified opt-in change, see Complexity Tracking) |
| II. Exactly one route | 3 mutually exclusive categories, tie-break, stickiness | ✅ | ✅ [system-prompt contract](./contracts/system-prompt.md) §Routing |
| III. Grounded answers only | FAQ only via `{{FAQ}}`; hand-off when not covered | ✅ | ✅ validator checks the placeholder |
| IV. Complete before calling | 3 fields, one question per turn, relay `ticketId` | ✅ | ✅ contract §Bug report + multi-turn verifier |
| V. Injection-resistant | Prompt hardening + additive guardrail | ✅ | ✅ guardrail is opt-in and documented; prompt works without it |
| VI. Evidence-driven | Suite covers all routes and edge cases; real scores in observations | ✅ | ✅ `run_bedrock_eval.py` prints real per-record scores; no fabricated numbers |
| Platform constraints | us-east-1, Nova Pro pinned, target `bugreports`, stack names | ✅ | ✅ |
| Workflow gates | Offline validator before commits; Conventional Commits | ✅ | ✅ CI workflow |

**Result**: PASS. No unjustified violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-support-chatbot-routing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── system-prompt.md      # Behavioral contract of the prompt
│   ├── test-suite.schema.json# harness-tests.json schema
│   ├── bug-report-tool.md    # Tool I/O as seen by the model and the Lambda
│   └── cli.md                # CLI contracts for the new and modified scripts
├── checklists/requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
project/
├── starter/                         # Run every project command from here
│   ├── system_prompt.txt            # MAIN DELIVERABLE (rewritten)
│   ├── online_shop_faq.md           # + new entries 33–34 (phone line, gift cards)
│   ├── harness-tests.json           # NEW: 24-case suite
│   ├── harness-tests-template.json  # unchanged
│   ├── cloudformation-tool.yaml     # unchanged
│   ├── cloudformation-testing.yaml  # unchanged
│   ├── cloudformation-guardrail.yaml# NEW: Bedrock Guardrail + version
│   ├── create_bug_report.py         # unchanged
│   ├── setup_gateway.py             # unchanged
│   ├── create_harness.py            # unchanged
│   ├── chat.py                      # + opt-in --guardrail flag
│   ├── generate-eval-dataset.py     # + opt-in --guardrail flag
│   ├── cleanup_agentcore.py         # unchanged
│   ├── guardrail.py                 # NEW: ApplyGuardrail wrapper (shared)
│   ├── setup_guardrail.py           # NEW: reads guardrail stack outputs → agentcore_config.json
│   ├── multiturn_bug_test.py        # NEW: scripted multi-turn verifier
│   ├── run_bedrock_eval.py          # NEW: upload + create job + poll + per-record scores
│   ├── mask_evidence.py             # NEW: copy evidence with masked account ID
│   ├── validate_offline.py          # NEW: offline quality gate
│   ├── requirements.txt             # unchanged
│   └── requirements-dev.txt         # NEW: pytest
├── tests/                           # NEW: pytest (offline, stubbed AWS)
│   ├── conftest.py
│   ├── test_validate_offline.py
│   ├── test_guardrail.py
│   └── test_multiturn_helpers.py
└── evidence/                        # NEW: rubric evidence (masked)
    ├── README.md                    # evidence index mapped to the rubric
    ├── observations.md              # evaluation observations (owner fills in with real scores)
    └── transcripts/                 # chat.py transcripts (owner)
.github/workflows/ci.yml             # NEW: offline gates on push/PR
README.md                            # Runbook
```

**Structure Decision**: keep the course layout (`project/starter/` is the working directory
for every command, as the brief requires) and add new files next to the scripts they
complement. Offline tests live in `project/tests/` and import the starter modules by path.
Evidence lives in `project/evidence/` so reviewers find everything in one place.

## Phase 0 / Phase 1 artifacts

- [research.md](./research.md): R1–R11 (guardrail placement, prompt architecture, test design,
  evaluation helper, evidence masking, CI)
- [data-model.md](./data-model.md): entities, fields, validation rules, conversation state
  machine
- [contracts/](./contracts/): prompt behavioral contract, test-suite schema, tool I/O, CLI
- [quickstart.md](./quickstart.md): end-to-end validation scenarios

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Opt-in `--guardrail` flag added to `chat.py` and `generate-eval-dataset.py` (course scripts) | FR-017 requires the guardrail to run before any model sees the message; the harness API has no guardrail parameter (R1) | Duplicating both scripts into `guarded_*.py` would fork about 250 lines of course code. The undocumented hook and `additionalParams` routes risk breaking the graded harness. Without the flag, behavior is byte-for-byte unchanged |
