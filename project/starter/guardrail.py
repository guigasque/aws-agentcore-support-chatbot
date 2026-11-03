"""Client-side Amazon Bedrock Guardrail check for customer messages.

The managed harness has no guardrail parameter, so the course scripts call
ApplyGuardrail on each customer message BEFORE invoking the harness (opt-in
with --guardrail). ApplyGuardrail evaluates the text without calling any
model. If the guardrail intervenes, the harness is not called at all.

Callers must fail closed: if check_input raises, do not invoke the harness.
"""

from typing import NamedTuple, Optional, Tuple


class GuardrailResult(NamedTuple):
    blocked: bool
    message: Optional[str]
    raw: dict


def load_guardrail(config: dict) -> Optional[Tuple[str, str]]:
    """Return (guardrail_id, guardrail_version) from the config, or None."""
    guardrail_id = config.get("guardrail_id")
    version = config.get("guardrail_version")
    if not guardrail_id or not version:
        return None
    return guardrail_id, str(version)


def check_input(client, guardrail_id: str, version: str, text: str) -> GuardrailResult:
    """Evaluate a customer message with the guardrail.

    client is a boto3 "bedrock-runtime" client. Errors are raised as-is.
    """
    response = client.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=version,
        source="INPUT",
        content=[{"text": {"text": text}}],
    )
    blocked = response.get("action") == "GUARDRAIL_INTERVENED"
    message = None
    if blocked:
        outputs = response.get("outputs") or []
        message = outputs[0].get("text") if outputs else None
    return GuardrailResult(blocked=blocked, message=message, raw=response)
