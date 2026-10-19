# AgentCore Support Chatbot

Customer support chatbot for a fictional online shop. It runs on the **Amazon Bedrock AgentCore
managed harness** and is built with **Spec-Driven Development** using
[GitHub Spec Kit](https://github.com/github/spec-kit).

A single system prompt routes each customer message to one of three behaviors:

| Route | Behavior |
|-------|----------|
| Bug report | Collect the description, steps to reproduce and environment one question at a time, then file a ticket with `create_bug_report` (Lambda → DynamoDB via an AgentCore Gateway) and give the customer the ticket ID |
| Platform question | Answer only from the embedded shop FAQ, and hand off to the support line when the FAQ doesn't cover the question |
| Other | Redirect the customer politely to the human support phone line |

> Status: **specification phase**. The full runbook will be added during `/speckit-implement`.

## Repository layout

```
.specify/                 Spec Kit config, templates, constitution (.specify/memory/constitution.md)
.agents/skills/           Spec Kit skills (/speckit-*) for the coding agent
specs/001-support-chatbot-routing/
  spec.md                 Feature specification (WHAT / WHY)
  checklists/             Spec quality checklists
project/starter/          Course starter files (run every project command from here)
```

## Spec-Driven workflow

`/speckit-constitution` ✅ → `/speckit-specify` ✅ → `/speckit-clarify` → `/speckit-plan` →
`/speckit-tasks` → `/speckit-analyze` → `/speckit-implement`

## Credits

The starter code comes from
[udacity/aws-c1-prompting-llm-reasoning-nd905-cd14762-project](https://github.com/udacity/aws-c1-prompting-llm-reasoning-nd905-cd14762-project)
and is distributed under the terms in [LICENSE.md](LICENSE.md).
