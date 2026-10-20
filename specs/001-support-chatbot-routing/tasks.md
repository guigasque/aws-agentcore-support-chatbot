# Tasks: Customer Support Chatbot Routing

**Input**: Design documents from `specs/001-support-chatbot-routing/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Requested by the spec (FR-021 offline validator, FR-022 multi-turn verifier) and the
constitution (offline gates). Offline tests are written before the code they cover.

**Organization**: Tasks are grouped by user story. Paths are relative to the repository root.
`[OWNER]` marks steps that need AWS credentials and are run by the repository owner.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US5 from spec.md

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create `project/starter/requirements-dev.txt` with `-r requirements.txt` and `pytest>=8`
- [ ] T002 Create `project/tests/conftest.py` that adds `project/starter/` to `sys.path` and exposes a `load_module(name, filename)` helper using `importlib.util` (needed for the hyphenated `generate-eval-dataset.py`)
- [ ] T003 [P] Create `.github/workflows/ci.yml`: on push/PR, Python matrix 3.9 and 3.12, install `project/starter/requirements-dev.txt`, run `python validate_offline.py` (working dir `project/starter`) and `python -m pytest project/tests -q`
- [ ] T004 [P] Create `project/evidence/README.md` (an evidence index that maps every rubric evidence item to a file path, marked TODO until produced) and `project/evidence/transcripts/.gitkeep`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: All user stories depend on the validator, the FAQ entries and the prompt skeleton.

- [ ] T005 Write `project/tests/test_validate_offline.py` covering every check in contracts/cli.md: prompt S1–S6 (placeholder exactly once inside `<faq>`, no `#` lines, the 3 route names, phone `+1 (800) 555-0199`, tool `bugreports___create_bug_report`, rendered ≤ 32,000 chars); test suite: schema per `contracts/test-suite.schema.json` (`id` pattern `^[a-z]+(_[a-z0-9]+)+$`, unique ids, `route` enum, `expected` minLength 20), minimum counts `bug ≥ 3, faq ≥ 4, faq_miss ≥ 2, other ≥ 3, edge ≥ 3, injection ≥ 2, faq_ext ≥ 1; total ≥ 18`, id prefix consistent with route; FAQ: entries `33)` and `34)` exist. Use both passing and failing fixtures; tests must fail first
- [ ] T006 Implement `project/starter/validate_offline.py` (standard library only) with `check_prompt(text, faq)`, `check_tests(obj)`, `check_faq(text)` and a CLI printing PASS/FAIL per check, exit code 0/1 (makes T005 pass)
- [ ] T007 [P] Extend `project/starter/online_shop_faq.md`: add `33) What is the customer support phone number?` (answer: `+1 (800) 555-0199`, Monday–Friday excluding holidays) under "Account & Support", and `34) Do you sell gift cards?` (answer: not currently; promotions are applied with promo codes at checkout) under "Payments & Promotions"
- [ ] T008 Rewrite `project/starter/system_prompt.txt` skeleton: remove all starter `#` comments; add the `<role>`, `<security>` (X1–X3), `<routing>` (R1–R6 with BUG_REPORT / PLATFORM_QUESTION / OTHER, includes/excludes/examples, tie-break, stickiness), `<handoff>` (H1) and a final `<faq>{{FAQ}}</faq>` block, per research R3 and contracts/system-prompt.md

**Checkpoint**: `python validate_offline.py` passes the prompt and FAQ checks (the suite check can still fail until the stories add tests).

---

## Phase 3: User Story 1 - Report a bug and receive a ticket ID (P1) 🎯 MVP

**Goal**: multi-turn collection of the 3 fields, a single tool call, and the ticket ID relayed.

**Independent Test**: quickstart V2. `multiturn_bug_test.py` passes and the DynamoDB item
matches the conversation.

- [ ] T009 [P] [US1] Write `project/tests/test_multiturn_helpers.py`: `extract_ticket_id` returns the UUID4 from text and `None` if absent; `field_matches(value, keywords)` is case-insensitive and requires all keywords; the scripted-turn structure is non-empty and includes a description, steps and environment turn
- [ ] T010 [US1] Add `<bug_report_procedure>` to `project/starter/system_prompt.txt` implementing B1–B9 (order description → steps → environment, one question per turn, vagueness follow-up, no placeholder values like `unknown`/`N/A`, single call to `bugreports___create_bug_report`, relay `ticketId` verbatim, error handling, no duplicates, abandonment)
- [ ] T011 [P] [US1] Create `project/starter/harness-tests.json` with the first 3 `bug` tests (`bug_checkout_crash`, `bug_login_error`, `bug_full_details`); the `expected` text for the partial reports says "acknowledges and asks ONE question for a missing detail; does NOT claim a ticket was created"
- [ ] T012 [US1] Implement `project/starter/multiturn_bug_test.py` per contracts/cli.md: reuse `chat.invoke`, session id `<uuid4>-multiturn`, scripted turns with keywords, assert no `[tool call]` before the final turn (wrap stdout capture), extract the ticket id, read with `dynamodb.get_item` on `table_name`, assert the field keywords, `--transcript-out`, `--guardrail` passthrough, exit 0/1 (makes T009 pass)
- [ ] T013 [US1] [OWNER] Deploy the tool stack, run `setup_gateway.py` and `create_harness.py`, run a manual bug conversation with `chat.py`, and save the transcript to `project/evidence/transcripts/bug_report.txt`, plus a screenshot of the DynamoDB item to `project/evidence/dynamodb_ticket.png`; run `multiturn_bug_test.py --transcript-out ../evidence/transcripts/multiturn_bug.txt`

**Checkpoint**: US1 works end to end, which delivers the MVP.

---

## Phase 4: User Story 2 - Get an answer to a platform question (P1)

**Goal**: answers grounded in the FAQ, and a hand-off when the FAQ doesn't cover the question.

**Independent Test**: quickstart V3.

- [ ] T014 [US2] Add `<faq_procedure>` to `project/starter/system_prompt.txt` implementing F1–F4 (FAQ-only answers, no access to order data, uncovered → hand-off H1, damaged item → FAQ 16)
- [ ] T015 [P] [US2] Append to `project/starter/harness-tests.json`: `faq` ×4 (`faq_return_window`, `faq_track_order`, `faq_payment_declined`, `faq_shipping_cost`), `faq_miss` ×2 (`faqmiss_drone_battery`, `faqmiss_price_match`), `faq_ext` ×1 (`ext_gift_cards`, which must say no gift cards are sold, per FAQ 34) — the faq_miss/faq_ext id prefixes must be accepted by the validator's prefix-route mapping
- [ ] T016 [US2] [OWNER] Save `chat.py` transcripts for a covered question and an uncovered question to `project/evidence/transcripts/faq_covered.txt` and `project/evidence/transcripts/faq_uncovered.txt`

---

## Phase 5: User Story 3 - Be redirected for out-of-scope requests (P2)

**Independent Test**: quickstart V4 (poem request → polite redirect with phone line).

- [ ] T017 [US3] Complete the OTHER behavior in `project/starter/system_prompt.txt` (H2 1–3 sentence redirect, H3 greeting) and add `<examples>` with one short example per route
- [ ] T018 [P] [US3] Append `other` ×3 (`other_poem`, `other_legal_advice`, `other_human_request`) to `project/starter/harness-tests.json`
- [ ] T019 [US3] [OWNER] Save an out-of-scope `chat.py` transcript to `project/evidence/transcripts/out_of_scope.txt`

---

## Phase 6: User Story 4 - Resist manipulation and harmful input (P2)

**Independent Test**: quickstart V4 injection checks plus V5 guardrail.

- [ ] T020 [P] [US4] Write `project/tests/test_guardrail.py` with `botocore.stub.Stubber` on a `bedrock-runtime` client: `GUARDRAIL_INTERVENED` → `blocked=True` with the message from `outputs[0].text`; `NONE` → `blocked=False`; `load_guardrail` returns `None` when the keys are missing and a tuple when they're present; the request uses `source="INPUT"` and `content=[{"text": {"text": ...}}]`
- [ ] T021 [P] [US4] Create `project/starter/cloudformation-guardrail.yaml`: `AWS::Bedrock::Guardrail` (content filters HATE/INSULTS/SEXUAL/VIOLENCE/MISCONDUCT input HIGH and output HIGH; PROMPT_ATTACK input HIGH and output NONE; polite blocked input/output messaging that includes `+1 (800) 555-0199`) and `AWS::Bedrock::GuardrailVersion`; outputs `GuardrailId`, `GuardrailVersion`
- [ ] T022 [US4] Implement `project/starter/guardrail.py` (`GuardrailResult`, `load_guardrail`, `check_input`) per contracts/cli.md (makes T020 pass)
- [ ] T023 [US4] Implement `project/starter/setup_guardrail.py` (reads the outputs of `bug-report-guardrail-stack` and merges `guardrail_id`/`guardrail_version` into `agentcore_config.json`)
- [ ] T024 [US4] Add the opt-in `--guardrail` flag to `project/starter/chat.py` and `project/starter/generate-eval-dataset.py` (no behavior change without the flag; when blocked, `chat.py` prints `[guardrail blocked] <message>` and the dataset uses the message as `response`; fail closed on errors)
- [ ] T025 [US4] Harden `<security>` in `project/starter/system_prompt.txt` with X4 (embedded instructions inside bug reports ignored) and add one injection example to `<examples>`
- [ ] T026 [P] [US4] Append `injection` ×2 (`inj_ignore_instructions`, `inj_fake_ticket`) and `edge` ×4 (`edge_cant_pay` ambiguous, `edge_help` very short, `edge_damaged_item` physical damage → returns FAQ, `edge_portuguese` other language) to `project/starter/harness-tests.json`, reaching 24 tests
- [ ] T027 [US4] [OWNER] Deploy the guardrail stack, run `setup_guardrail.py`, and verify `chat.py --guardrail` blocks an injection but not a legitimate bug report; save the transcript to `project/evidence/transcripts/guardrail.txt`

---

## Phase 7: User Story 5 - Verify quality with an automated evaluation (P1)

**Goal**: dataset with no errors, a completed evaluation job, per-record scores, and
observations.

**Independent Test**: quickstart V6. Depends on the full suite (T011, T015, T018, T026).

- [ ] T028 [P] [US5] Write tests in `project/tests/test_eval_helpers.py`: `mask_account_ids` replaces 12-digit account IDs inside ARNs and bare IDs but leaves UUIDs/timestamps intact; `extract_scores(record)` finds `Builtin.Correctness` at any nesting level and returns `None` when it's absent
- [ ] T029 [US5] Implement `project/starter/mask_evidence.py` (`mask_account_ids`, CLI `--out-dir`)
- [ ] T030 [US5] Implement `project/starter/run_bedrock_eval.py` per contracts/cli.md (testing stack outputs, S3 upload, `create_evaluation_job` with the exact config from the brief, `--wait` polling, download results, `extract_scores`, markdown table to `--scores-out`) (makes T028 pass)
- [ ] T031 [P] [US5] Create `project/evidence/observations.md` template: sections for the run summary, a per-record score table (to be pasted from `eval_scores.md`), analysis by route, judge disagreements, and prompt changes made or planned. It must state explicitly that no numbers are filled in before a real run
- [ ] T032 [US5] [OWNER] Run `generate-eval-dataset.py --tests-json harness-tests.json` (0 `[HARNESS_ERROR]`), deploy the testing stack, run `run_bedrock_eval.py --wait --scores-out ../evidence/eval_scores.md` and `mask_evidence.py`, screenshot the job results page to `project/evidence/eval_job_results.png`, then write the observations together with the agent from the real scores

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T033 Rewrite `README.md` as the full runbook (prerequisites, setup, build, chat, multi-turn test, guardrail, evaluation, evidence, cleanup including `bug-report-guardrail-stack`, troubleshooting) and the rubric → evidence map
- [ ] T034 [P] Update `project/evidence/README.md` links once the files exist
- [ ] T035 Run `python validate_offline.py` and `python -m pytest project/tests -q` locally; fix any failures
- [ ] T036 Run `/speckit-analyze` for cross-artifact consistency, then mark the completed tasks in this file

---

## Dependencies & Execution Order

- Setup (T001–T004) → Foundational (T005–T008) → user stories.
- US1, US2, US3 and US4 each edit `system_prompt.txt` and `harness-tests.json`, so their edits
  to those files are sequential (T010 → T014 → T017 → T025; T011 → T015 → T018 → T026). Their
  other files are independent.
- US4's guardrail tooling (T020–T024) is independent of the prompt work.
- US5 code (T028–T031) can be built at any time. The run (T032) needs the full suite and the
  online steps of US1–US4.
- `[OWNER]` tasks need a deployed environment: T013 first, because it creates the stack,
  gateway and harness.

## Parallel Example

```text
After T008:  T009 (multiturn tests) ‖ T020 (guardrail tests) ‖ T021 (guardrail CFN) ‖ T028 (eval helper tests)
Then:        T012 ‖ T022 ‖ T029/T030   (different files)
```

## Implementation Strategy

1. **MVP**: Phases 1–3 deliver a working bug route with a verified ticket.
2. Add US2 and US3, which completes the three graded routes.
3. Add US4 (stand-out hardening and guardrail).
4. Run US5 on the full suite and iterate on the prompt using the real scores.
5. Polish: README and evidence.
