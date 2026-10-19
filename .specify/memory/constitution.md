<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Principles defined: I. The Prompt Is the Product; II. Exactly One Route;
  III. Grounded Answers Only; IV. Complete Before Calling; V. Injection-Resistant by Default;
  VI. Evidence-Driven Quality
- Added sections: Platform & Security Constraints; Development Workflow & Quality Gates
- Removed sections: none
- Templates requiring updates: none (plan/spec/tasks templates read this file at runtime)
- Deferred TODOs: none
-->

# AgentCore Support Chatbot Constitution

## Core Principles

### I. The Prompt Is the Product

All routing, information-gathering and grounding behavior MUST live in
`project/starter/system_prompt.txt`. There MUST NOT be separate classifiers, condition nodes,
extra agents or client-side routing logic. The course-provided infrastructure scripts
(`setup_gateway.py`, `create_harness.py`, `chat.py`, `generate-eval-dataset.py`,
`cleanup_agentcore.py`, CloudFormation templates, Lambda) MUST stay functionally unchanged;
any modification requires a written justification in the plan's Complexity Tracking table.
New tooling (validators, scripted conversations, guardrail setup) MUST be additive and live in
new files.

*Rationale*: the rubric evaluates prompt engineering; changing the harness contract would
invalidate the evaluation and the evidence.

### II. Exactly One Route

Every customer message MUST be classified into exactly one of three mutually exclusive
categories before any response is produced: **Bug report**, **Platform question**
(orders, shipping, returns, payments and the other FAQ topics), or **Other**. Category
definitions MUST be crisp, include positive and negative examples, and define a deterministic
tie-break rule for ambiguous messages. Once a bug-report collection is in progress, the session
MUST remain on that route until the ticket is filed or the customer explicitly abandons it.

*Rationale*: vague categories produce vague routing; predictability across the test suite is a
graded criterion.

### III. Grounded Answers Only

Platform questions MUST be answered only from the FAQ injected through the `{{FAQ}}`
placeholder. The chatbot MUST NOT invent policies, prices, timelines, phone numbers beyond the
configured support line, or order-specific facts. When the FAQ does not cover a question, the
chatbot MUST hand off to the human support phone line instead of guessing. The `{{FAQ}}`
placeholder MUST remain in the prompt; the FAQ content MUST NOT be pasted manually.

*Rationale*: hallucinated policy answers are the highest-impact failure for a support bot.

### IV. Complete Before Calling

The `create_bug_report` tool (seen by the model as `bugreports___create_bug_report`) MUST be
called only after all three fields — `description`, `stepsToReproduce`, `environment` — have
been provided by the customer. The chatbot MUST ask for missing fields one question at a time,
MUST NOT fabricate or infer field values the customer did not state, and MUST relay the
returned `ticketId` verbatim after a successful call. Tool errors MUST lead to asking for the
missing information or a hand-off, never to a fake ticket ID.

*Rationale*: incomplete or invented tickets waste engineering time and fail the rubric.

### V. Injection-Resistant by Default

Customer messages are untrusted data. The system prompt MUST state that instructions inside
customer messages cannot change the chatbot's role, rules, categories or tools, and MUST NOT
reveal the system prompt or internal tool names. Attempts such as "ignore your previous
instructions" MUST be handled as the **Other** route with a polite redirect. Where a Bedrock
Guardrail is added, it MUST be additive and documented, and MUST NOT block legitimate bug
reports or FAQ questions.

*Rationale*: a public-facing chatbot will receive adversarial input; hardening is a stand-out
criterion.

### VI. Evidence-Driven Quality

`harness-tests.json` MUST cover all three routes plus edge cases (ambiguous, very short,
uncovered FAQ question, prompt injection, multilingual where relevant). Each `expected` field
MUST describe single-turn intent (for bug reports: the start of collection, not a finished
ticket). Any change to `system_prompt.txt` MUST be followed by regenerating the dataset and,
for submission, a Bedrock Evaluations job using `Builtin.Correctness`. Written observations
MUST cite actual per-record scores — never placeholder or fabricated numbers.

*Rationale*: the evaluation evidence is a graded deliverable and the only objective signal of
prompt quality.

## Platform & Security Constraints

- Region MUST be `us-east-1` for every resource, script and command.
- Model MUST be pinned to `us.amazon.nova-pro-v1:0` (harness and invokes); the evaluator model
  is `amazon.nova-pro-v1:0`. The harness default model MUST NOT be relied upon.
- Python 3.9+ with `boto3`/`botocore` 1.43.76+ as pinned in `requirements.txt`.
- Gateway target name MUST be `bugreports` (letters, digits, underscores only).
- Stack names MUST remain `bug-report-tool-stack` and `bug-report-testing-stack`.
- AWS credentials, access keys and session tokens MUST NEVER be committed. Evidence files that
  contain ARNs may be committed with the AWS account ID masked.
- All AWS-mutating commands (deploy, create, delete) are executed by the repository owner, not by
  automation in this repository; documentation MUST give exact, copy-pasteable commands.

## Development Workflow & Quality Gates

- Work follows the Spec Kit flow: constitution → specify → (clarify) → plan → tasks →
  (analyze) → implement. Specs and plans live under `specs/`.
- Repository artifacts (specs, docs, prompt, tests) are written in English to match the course
  rubric; conversation with the owner may be in Portuguese.
- Offline gates MUST pass before every commit that touches the prompt or tests: a local
  validator checks that `system_prompt.txt` contains `{{FAQ}}`, contains no leftover starter
  comment lines, defines the three categories, and that `harness-tests.json` is valid JSON with
  unique IDs covering all three routes.
- Online gates (run by the owner): manual `chat.py` transcripts for each route, a DynamoDB
  ticket created by the chatbot, `generate-eval-dataset.py` output with zero `[HARNESS_ERROR]`
  entries, and a completed evaluation job.
- Commits use Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).

## Governance

This constitution supersedes ad-hoc practices for this repository. Every plan MUST include a
Constitution Check against Principles I–VI; violations MUST be justified in Complexity Tracking or
removed. Amendments require updating this file with a new Sync Impact Report and a semantic
version bump (MAJOR: principle removed or redefined; MINOR: principle or section added;
PATCH: clarification). Compliance is reviewed at `/speckit-analyze` time and before submission.
Runtime guidance for contributors lives in `README.md`.

**Version**: 1.0.0 | **Ratified**: 2026-10-19 | **Last Amended**: 2026-10-19
