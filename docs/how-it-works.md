# How the support chatbot works

This document explains the chatbot step by step: what gets built once, what happens on every
customer message, how the behavior is checked, and how to clean up. For the exact commands, see
the runbook in the [README](../README.md).

## Overview

The chatbot is a single system prompt ([`system_prompt.txt`](../project/starter/system_prompt.txt))
running on the Amazon Bedrock AgentCore managed harness with Amazon Nova Pro. There is no
separate classifier. For each message, the model picks one of three routes:

| Route | Behavior |
|-------|----------|
| Bug report | Collect the description, steps to reproduce and environment, one question at a time, then file a ticket and give the customer the ticket ID |
| Shop question | Answer only from the embedded FAQ; hand off to +1 (800) 555-0199 when the FAQ doesn't cover it |
| Anything else | Politely redirect to the support line |

```
customer ─▶ chat.py ─▶ [guardrail, optional] ─▶ AgentCore harness (Nova Pro + system prompt)
                                                      │
                                                      ▼ tool call
                                AgentCore Gateway ─▶ Lambda create_bug_report ─▶ DynamoDB
```

## Build (once)

1. **Deploy the tool stack.** [`cloudformation-tool.yaml`](../project/starter/cloudformation-tool.yaml)
   creates three things:
   - the DynamoDB table `bug-report-tool-stack-bug-reports`;
   - the Lambda function `create_bug_report`, which validates the three fields and writes a
     ticket with a new UUID;
   - IAM roles for the Lambda, the gateway and the harness.
2. **Create the gateway.** [`setup_gateway.py`](../project/starter/setup_gateway.py) creates an
   AgentCore Gateway and registers the Lambda as a target named `bugreports`, with a JSON schema
   listing the three required fields. The model sees the tool as
   `bugreports___create_bug_report`. The script saves the ARNs to `agentcore_config.json`.
3. **Build the harness.** [`create_harness.py`](../project/starter/create_harness.py) reads
   `system_prompt.txt` and replaces `{{FAQ}}` with the contents of
   [`online_shop_faq.md`](../project/starter/online_shop_faq.md). It then creates the managed
   harness with Nova Pro set to temperature 0 and topK 1, so answers are deterministic. The
   harness is AWS's hosted agent loop: it runs the model, calls tools and keeps the
   conversation history.

## Every message

1. **The customer types** into [`chat.py`](../project/starter/chat.py). A run of `chat.py` is
   one conversation, identified by a session ID. The same ID is also sent as the `actorId`, so
   the harness's long-term memory never mixes customers.
2. **Guardrail (optional).** With `--guardrail`, the message goes to Bedrock's `ApplyGuardrail`
   first ([`guardrail.py`](../project/starter/guardrail.py)). If it's harmful or a prompt
   attack, the client prints a fixed blocked message and the model never sees it.
3. **The client calls `invoke_harness`** with the message, the session ID and the gateway, so
   the model can use the tool.
4. **The model picks a route.** The prompt has it choose one of three, with tie-break rules for
   ambiguous cases:
   - **Bug report:** the website or app is broken.
   - **Shop question:** how-to, policy or status questions.
   - **Anything else:** off-topic requests, injection attempts, harmful content.
5. **The model follows that route's rules:**
   - **Shop question:** answer only from the FAQ text in the prompt. If the FAQ doesn't cover
     it, say so and give +1 (800) 555-0199.
   - **Anything else:** a 1–3 sentence polite redirect with the phone line.
   - **Bug report:** this route spans several turns. Before each reply, the model writes a
     checklist in its `<thinking>` block: description, steps and environment, each either
     quoted from the customer or marked MISSING. If anything is MISSING, it asks one question
     and stops. The harness remembers the earlier turns, so each reply fills one more field.
6. **The ticket is filed.** Once nothing is MISSING, the model calls
   `bugreports___create_bug_report`. The harness sends the call through the gateway to the
   Lambda, which writes the item to DynamoDB and returns `{"ticketId": ..., "status": "OPEN"}`.
   If a field is empty, the Lambda returns an error instead, and the model asks for it again.
7. **The model replies** with the ticket ID exactly as returned. `chat.py` streams the reply and
   prints `[tool call] bugreports___create_bug_report` when the tool runs.

Example of a complete bug report:

```
you> The checkout page crashes when I click Pay
bot> Sorry about that, and thanks for letting us know. What steps do you take before it crashes?
you> I add a jacket to the cart, go to checkout, enter my card and click Pay
bot> Thanks. Which browser and operating system are you using?
you> Chrome 120 on macOS Sonoma
[tool call] bugreports___create_bug_report
bot> Thanks! I've filed your report. Your ticket ID is <uuid>. Our engineering team will look into it.
```

## Checking that it works

1. **Offline:** [`validate_offline.py`](../project/starter/validate_offline.py) checks the
   prompt's structure and the test suite, and pytest ([`project/tests/`](../project/tests/))
   tests the helper scripts. Neither needs AWS.
2. **Multi-turn test:** [`multiturn_bug_test.py`](../project/starter/multiturn_bug_test.py)
   sends three scripted messages and checks that no tool call happens before the last one. It
   then reads the ticket from DynamoDB and compares each field with what was sent.
3. **Evaluation:**
   - [`generate-eval-dataset.py`](../project/starter/generate-eval-dataset.py) sends each of the
     24 test prompts in [`harness-tests.json`](../project/starter/harness-tests.json) in a fresh
     session and records the answers.
   - [`run_bedrock_eval.py`](../project/starter/run_bedrock_eval.py) has Nova Pro score each
     answer against the expected behavior (`Builtin.Correctness`).
   - [`observations.md`](../project/evidence/observations.md) analyzes the scores and the
     prompt changes they led to.

## Cleanup

Run `cleanup_agentcore.py` to delete the harness and gateway, then delete the CloudFormation
stacks. The evaluation bucket must be emptied before its stack can be deleted. The full
sequence is in README step 9.
