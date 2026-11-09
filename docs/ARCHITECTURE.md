# Architecture — AgentCore Support Chatbot

Mermaid diagrams and notes for the single-prompt support chatbot. The diagrams are text, so they
diff cleanly and render on GitHub. For a plain-language walkthrough, start with
[`how-it-works.md`](how-it-works.md). The authoritative design is in
[`../specs/001-support-chatbot-routing/plan.md`](../specs/001-support-chatbot-routing/plan.md) and
the behavior contract in
[`../specs/001-support-chatbot-routing/contracts/system-prompt.md`](../specs/001-support-chatbot-routing/contracts/system-prompt.md).

---

## (a) System architecture

One AgentCore managed harness runs Amazon Nova Pro with the system prompt. There are no worker
agents and no separate classifier: routing, bug collection and FAQ grounding all happen inside that
one prompt. The only tool is `create_bug_report`, exposed to the model through an AgentCore Gateway
that invokes a Lambda function, which writes to DynamoDB. The guardrail is applied by the client
before the harness is called, because the harness API has no guardrail parameter.

```mermaid
flowchart LR
    client["chat.py / generate-eval-dataset.py<br/>multiturn_bug_test.py"] -. "--guardrail (optional)" .-> gr["Bedrock Guardrail<br/>ApplyGuardrail · INPUT"]
    client -->|"invoke_harness<br/>runtimeSessionId + actorId"| h["AgentCore managed harness<br/>support_chatbot"]

    subgraph harness["Harness"]
        m["Amazon Nova Pro<br/>us.amazon.nova-pro-v1:0<br/>temperature 0 · topK 1"]
        sp["System prompt<br/>routing · bug procedure · FAQ rules<br/>FAQ inserted via {{FAQ}}"]
        mem["Managed memory<br/>per-actor facts + session summaries"]
    end
    h --- m
    m --- sp
    h --- mem

    m -->|"tool call<br/>bugreports___create_bug_report"| gw["AgentCore Gateway<br/>MCP · AWS_IAM auth<br/>target: bugreports"]
    gw -->|"lambda:InvokeFunction"| fn["Lambda<br/>bug-report-tool-stack-create-bug-report<br/>python3.12"]
    fn -->|"dynamodb:PutItem"| ddb[("DynamoDB<br/>bug-report-tool-stack-bug-reports<br/>PK ticketId")]
    h -. logs .-> cw["CloudWatch Logs"]
    fn -. logs .-> cw
```

The tool stack (DynamoDB, Lambda, three IAM roles) comes from CloudFormation. The gateway and the
harness are created by the course's boto3 scripts (`setup_gateway.py`, `create_harness.py`), which
write their IDs to `agentcore_config.json`.

---

## (b) Bug report flow (multi-turn)

The harness keeps the conversation for one `runtimeSessionId`, so details collected in earlier turns
are still available later. Before each reply, the model writes a checklist in `<thinking>` (rule B0).
It may call the tool only when no field is MISSING and no ticket has been filed yet in this
conversation.

```mermaid
sequenceDiagram
    autonumber
    participant C as Customer (chat.py)
    participant H as Harness (Nova Pro)
    participant G as Gateway
    participant L as Lambda
    participant D as DynamoDB

    C->>H: "The checkout page crashes when I click Pay"
    Note over H: B0: description ✓ · steps MISSING · environment MISSING
    H-->>C: one question: what steps lead to the crash?
    C->>H: "I add a jacket to the cart, go to checkout, enter my card and click Pay"
    Note over H: B0: description ✓ · steps ✓ · environment MISSING
    H-->>C: one question: which browser and operating system?
    C->>H: "Chrome 120 on macOS Sonoma"
    Note over H: B0: nothing MISSING, no ticket yet → call the tool once
    H->>G: bugreports___create_bug_report(description, stepsToReproduce, environment)
    G->>L: invoke (tool arguments as the event)
    L->>D: PutItem {ticketId, 3 fields, status OPEN, createdAt}
    L-->>G: {"ticketId": "<uuid4>", "status": "OPEN"}
    G-->>H: tool result
    H-->>C: "Your ticket ID is <uuid4>…" (relayed verbatim)
```

If a field arrives empty, the Lambda returns `{"error": "missing required field(s): …"}` instead of
writing, and the model asks the customer for that field (rule B7). That check backs up the prompt
rule rather than replacing it.

---

## (c) Routing decision (inside the prompt)

Greedy decoding (temperature 0, topK 1) makes routing repeatable. The model picks exactly one route
per message, silently. The route names are internal labels and are never shown to the customer.

```mermaid
flowchart TD
    msg(["Customer message"]) --> sticky{"Bug report already<br/>being collected?"}
    sticky -->|"yes, and the reply adds bug details"| bug
    sticky -->|"yes, but it's a FAQ question"| faqmid["answer briefly from the FAQ,<br/>then re-ask the missing field"]
    sticky -->|no| q{"What is it about?"}
    q -->|"website or app malfunction<br/>(error, crash, button, page)"| bug["BUG_REPORT<br/>B0–B9 collection procedure"]
    q -->|"policy, status or how-to<br/>(orders, shipping, returns, payments…)"| faq["PLATFORM_QUESTION<br/>F1–F5: answer only from the FAQ"]
    q -->|"off-topic, human request,<br/>injection attempt, harmful"| other["OTHER<br/>H2: 1–3 sentence redirect"]
    q -->|"still ambiguous<br/>(e.g. 'I can't pay')"| clarify["ask ONE clarifying question<br/>(no tool call, no hand-off)"]
    faq -->|"FAQ doesn't cover it"| handoff["H1: +1 (800) 555-0199<br/>Monday–Friday"]
    other --> handoff
    bug -->|"tool error other than a missing field"| handoff
```

Two edge cases are worth calling out. A damaged physical item is a returns question (FAQ entry 16),
not a website bug (rule F4). A bare "refund" is answered with the refund timeline (FAQ 14), not the
return window (rule F5); that rule was added after evaluation run 1 scored it 0.

---

## (d) Guardrail path (optional, client-side)

With `--guardrail`, each customer message goes through `ApplyGuardrail` before the harness sees it.
`ApplyGuardrail` evaluates the text without invoking any model. If the guardrail check itself fails,
the client doesn't send the message (fail closed). The prompt's own injection rules (X1–X4) work
without the guardrail.

```mermaid
flowchart LR
    msg["customer message"] --> ag["ApplyGuardrail<br/>source=INPUT"]
    ag -->|"action: NONE"| inv["invoke_harness"]
    ag -->|"action: GUARDRAIL_INTERVENED"| blk["print / record the fixed blocked message<br/>(includes the support line)"]
    ag -->|"API error"| err["chat.py: [guardrail error], message not sent<br/>dataset: [HARNESS_ERROR] record"]

    subgraph policy["Guardrail policy (cloudformation-guardrail.yaml)"]
        cf["content filters, input HIGH / output HIGH:<br/>HATE · INSULTS · SEXUAL · VIOLENCE · MISCONDUCT"]
        pa["PROMPT_ATTACK: input HIGH / output NONE"]
        none["no denied topics, no word filters<br/>(to avoid blocking real bug reports)"]
    end
```

---

## (e) Memory and session isolation

The managed harness has AgentCore Memory with two long-term strategies: semantic facts stored under
`/actors/{actorId}/facts/` and session summaries under `/actors/{actorId}/summaries/{sessionId}/`.
Facts are keyed by actor, not by session. The course scripts originally sent no `actorId`, so every
session shared the `default` actor, and a ticket filed in one chat was recalled in later chats and
eval cases. The fix is to send `actorId = runtimeSessionId` on every invoke, which makes one
conversation equal one customer.

```mermaid
flowchart TD
    subgraph before["Before the fix: no actorId"]
        s1["session A (chat)"] --> d["actor 'default'"]
        s2["session B (eval case)"] --> d
        s3["session C (multi-turn test)"] --> d
        d --> f[("/actors/default/facts/<br/>ticket 1566a723…, Firefox 128…")]
        f -->|"recalled in every new session"| leak["'Your bug is already filed'<br/>for a new customer"]
    end
    subgraph after["After the fix: actorId = session id"]
        a1["session A"] --> fa[("/actors/A/facts/")]
        a2["session B"] --> fb[("/actors/B/facts/")]
        a3["session C"] --> fc[("/actors/C/facts/")]
    end
```

Memory extraction is eventually consistent, so a fact written in one turn may only be retrievable
seconds to minutes later. The 84 records already stored under `default` were deleted with
`BatchDeleteMemoryRecords`; the deletion took several seconds to show up in `ListMemoryRecords`.

---

## (f) Evaluation pipeline

Each of the 24 test cases runs in a fresh session (with its own actor), so cases can't influence
each other. The dataset uses Bedrock Evaluations' bring-your-own-inference format: the responses
were already produced by the harness, and the judge only scores them.

```mermaid
flowchart LR
    tests["harness-tests.json<br/>24 cases · id · route · prompt · expected"] --> val["validate_offline.py<br/>schema + route counts"]
    tests --> gen["generate-eval-dataset.py<br/>fresh session per case"]
    gen -->|"invoke_harness"| hh["harness"]
    gen --> jsonl["output_eval_dataset.jsonl<br/>prompt · referenceResponse · modelResponses"]
    jsonl --> run["run_bedrock_eval.py"]
    run -->|"upload"| s3[("S3<br/>udacity-agentic-engineer-c1-eval-&lt;acct&gt;")]
    run -->|"create_evaluation_job"| job["Bedrock Evaluations<br/>Builtin.Correctness<br/>judge: amazon.nova-pro-v1:0<br/>source: my-support-chatbot"]
    job -->|"results"| s3
    s3 -->|"download + extract_scores"| scores["eval_scores.md<br/>per-record table + mean"]
    scores --> obs["observations.md"]
    jsonl --> mask["mask_evidence.py<br/>12-digit account IDs → ************"]
```

Results: run 1 averaged 0.917 (failures: the memory leak and the refund answer). Run 2 averaged
0.958, with the only 0 on `edge_cant_pay`. Details are in
[`../project/evidence/observations.md`](../project/evidence/observations.md).

---

## (g) Deployment and teardown order

Resources are created in dependency order and deleted in reverse. The harness execution role lives
in the tool stack, so the harness must be deleted before that stack.

```mermaid
flowchart TD
    p0["load .env (lab credentials)<br/>aws sts get-caller-identity"] --> p1["validate_offline.py + pytest"]
    p1 --> p2["cloudformation deploy<br/>cloudformation-tool.yaml → bug-report-tool-stack"]
    p2 --> p3["setup_gateway.py<br/>gateway + target 'bugreports' → agentcore_config.json"]
    p3 --> p4["create_harness.py<br/>prompt + FAQ, Nova Pro pinned → harness ARN in config"]
    p4 --> p5["optional: cloudformation-guardrail.yaml + setup_guardrail.py"]
    p5 --> p6["cloudformation-testing.yaml → bug-report-testing-stack<br/>(eval bucket + bedrock-eval-role)"]
    p6 --> ev["evidence: transcripts, multi-turn test,<br/>dataset, evaluation job, mask_evidence.py"]
    ev --> t1["cleanup_agentcore.py<br/>harness → gateway target → gateway"]
    t1 --> t2["delete bug-report-tool-stack + wait"]
    t2 --> t3["empty eval bucket → delete bug-report-testing-stack + wait"]
    t3 --> t4["delete bug-report-guardrail-stack + wait"]
    t4 --> t5["delete evaluation jobs and leftover log groups,<br/>rm .env"]
```

Steps not covered by CloudFormation or `cleanup_agentcore.py` need explicit cleanup. These are the
evaluation jobs (they aren't stack resources) and the CloudWatch log groups that the harness runtime
and the Lambda create on first use. A finished evaluation job costs nothing to keep. While deployed,
the main costs are model calls (chat, eval generation, and the judge), DynamoDB and Lambda
on-demand usage, and log storage. None of the deployed resources has a large idle cost, but they
should still be torn down after the evidence is captured.

---

## (h) Configuration and credentials flow

`agentcore_config.json` is the state record: each setup script reads it and adds the IDs it
creates. The client scripts read the ARNs from it. Lab credentials come only from `.env`, which is
gitignored and loaded into the shell; no script reads it directly.

```mermaid
flowchart LR
    env[".env (gitignored)<br/>AWS_ACCESS_KEY_ID · SECRET · SESSION_TOKEN · REGION"] -->|"set -a; source ./.env"| shell["shell environment"]
    shell --> scripts["all scripts (boto3)"]
    cfn["bug-report-tool-stack outputs<br/>Lambda ARN · role ARNs · table name"] --> sg["setup_gateway.py"]
    sg -->|"writes gateway_id/arn, target, table_name, roles"| cfg[("agentcore_config.json<br/>(gitignored)")]
    ch["create_harness.py"] -->|"writes harness_id/arn, model_id"| cfg
    gcfn["bug-report-guardrail-stack outputs"] --> sgr["setup_guardrail.py"]
    sgr -->|"writes guardrail_id/version"| cfg
    cfg --> clients["chat.py · generate-eval-dataset.py<br/>multiturn_bug_test.py"]
    cfg --> me["mask_evidence.py"] --> ev["project/evidence/agentcore_config.json<br/>(masked, committed)"]
```

---

## AWS resources (reference)

| Resource | Name / pattern | Created by |
|---|---|---|
| DynamoDB table | `bug-report-tool-stack-bug-reports` (PK `ticketId`, on-demand) | `cloudformation-tool.yaml` |
| Lambda function | `bug-report-tool-stack-create-bug-report` (python3.12) | `cloudformation-tool.yaml` |
| IAM role (Lambda) | `bug-report-tool-stack-lambda-role`: `dynamodb:PutItem` on the table only | `cloudformation-tool.yaml` |
| IAM role (gateway) | `bug-report-tool-stack-gateway-role`: `lambda:InvokeFunction` on the function only | `cloudformation-tool.yaml` |
| IAM role (harness) | `bug-report-tool-stack-harness-role`: model invoke, logs, X-Ray, memory, gateway | `cloudformation-tool.yaml` |
| AgentCore Gateway | `bug-report-tool-stack-gateway` (MCP, AWS_IAM), target `bugreports` | `setup_gateway.py` |
| AgentCore harness | `support_chatbot` (Nova Pro pinned) plus its runtime and managed memory | `create_harness.py` |
| Bedrock Guardrail | `bug-report-guardrail-stack-guardrail` (numbered version) | `cloudformation-guardrail.yaml` (optional) |
| S3 bucket | `udacity-agentic-engineer-c1-eval-<acct>` | `cloudformation-testing.yaml` |
| IAM role (evaluation) | `bedrock-eval-role`: S3 access to the bucket, invoke Nova Pro | `cloudformation-testing.yaml` |
| Evaluation jobs | `support-chatbot-eval-run-<UTC timestamp>` | `run_bedrock_eval.py` |
| CloudWatch log groups | `/aws/lambda/bug-report-tool-stack-create-bug-report`, `/aws/bedrock-agentcore/runtimes/harness_support_chatbot-*` | created on first use |

**IAM scope.** The Lambda and gateway roles are scoped to single resource ARNs. The harness role
comes from the course template and is broader: it allows invoking any foundation model, uses `*` for
X-Ray and some logging actions, and includes Code Interpreter and AWS Marketplace permissions this
chatbot doesn't use. That's acceptable for a lab sandbox. For production, narrow it to the Nova Pro
inference profile, the specific gateway and memory ARNs, and the runtime's own log group, and drop
the unused actions.
