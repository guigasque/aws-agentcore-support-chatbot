# Evidence index

Every required submission item and where it lives. Files that contain AWS identifiers are
committed only as masked copies (`python mask_evidence.py`, run from `project/starter/`).

| Required item | Evidence | Status |
|---------------|----------|--------|
| Completed `system_prompt.txt` | [`../starter/system_prompt.txt`](../starter/system_prompt.txt) | Done |
| `agentcore_config.json` with the harness and gateway ARNs (masked) | [`agentcore_config.json`](agentcore_config.json) | Done |
| Bug-report transcript with follow-up questions and `[tool call] bugreports___create_bug_report` | [`transcripts/bug_report.txt`](transcripts/bug_report.txt) | **Redo**: current file starts with an injection test and stops after the first follow-up |
| DynamoDB table with an item created by the chatbot | [`img/dynamo.png`](img/dynamo.png), [`img/dynamo-cli.png`](img/dynamo-cli.png) | **Redo**: items come from the memory-leak sessions; account ID visible |
| Covered-question transcript | [`transcripts/faq_covered.txt`](transcripts/faq_covered.txt) | Done |
| Uncovered-question transcript | [`transcripts/faq_uncovered.txt`](transcripts/faq_uncovered.txt) | Done |
| Out-of-scope transcript | [`transcripts/out_of_scope.txt`](transcripts/out_of_scope.txt) | Done |
| `harness-tests.json` | [`../starter/harness-tests.json`](../starter/harness-tests.json) | Done |
| `output_eval_dataset.jsonl` (masked, run 2) | [`output_eval_dataset.jsonl`](output_eval_dataset.jsonl) | Done |
| Written observations | [`observations.md`](observations.md), per-record scores in [`eval_scores.md`](eval_scores.md) | Done |
| Completed evaluation job results page | [`img/evaluation.png`](img/evaluation.png), [`img/evaluation_bedrock.png`](img/evaluation_bedrock.png) | **Redo** for run 2 (current screenshots are run 1) |

Extras (not on the required list):

| Item | Evidence | Status |
|------|----------|--------|
| Scripted multi-turn bug report, checked against DynamoDB | [`transcripts/multiturn_bug.txt`](transcripts/multiturn_bug.txt) | **Redo**: current file is the failing pre-fix run |
| Guardrail blocks an injection but not a bug report | [`transcripts/guardrail.txt`](transcripts/guardrail.txt), [`img/guardrail.png`](img/guardrail.png) | **Redo**: second message recalled an old ticket (pre-fix) |
| Chat screenshots | [`img/chats.png`](img/chats.png) | Done |
| Offline quality gate | [`../starter/validate_offline.py`](../starter/validate_offline.py), [`../tests/`](../tests/) | Done |
