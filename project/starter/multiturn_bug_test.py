#!/usr/bin/env python3
"""Scripted multi-turn bug-report test against the deployed harness.

    python multiturn_bug_test.py [--guardrail] [--transcript-out ../evidence/transcripts/multiturn_bug.txt]

Sends a fixed conversation in ONE session, one bug detail per turn, and checks:
  1. no tool call happens before the final turn (nothing filed early);
  2. the final turn makes exactly one tool call and the reply contains a
     UUID ticket ID;
  3. the DynamoDB item for that ticket exists and each field contains the
     keywords of the turn that supplied it.

Exits 0 when every check passes, 1 otherwise.
"""

import argparse
import contextlib
import json
import re
import sys
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

from chat import invoke

TOOL_CALL_MARKER = "[tool call]"
UUID4_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)

# One bug detail per turn, in the order the prompt asks for them. The
# keywords are checked (case-insensitively) against the stored ticket field.
SCRIPT = [
    {
        "field": "description",
        "text": "The checkout page crashes when I click the Pay button.",
        "keywords": ["checkout", "pay"],
    },
    {
        "field": "stepsToReproduce",
        "text": "I add any item to the cart, go to checkout, enter my card details and click Pay.",
        "keywords": ["cart", "card"],
    },
    {
        "field": "environment",
        "text": "Firefox 128 on Windows 11, on a desktop PC.",
        "keywords": ["firefox", "windows"],
    },
]


def extract_ticket_id(text):
    """Return the first UUID4 in text, or None."""
    match = UUID4_RE.search(text or "")
    return match.group(0) if match else None


def field_matches(value, keywords):
    """True if value contains every keyword, ignoring case."""
    if not value:
        return False
    lowered = str(value).lower()
    return all(k.lower() in lowered for k in keywords)


class Tee:
    """File-like object that forwards writes and keeps a copy.

    chat.invoke() prints "[tool call] <name>" to stdout when the model calls
    a tool; capturing stdout is how this script detects tool calls.
    """

    def __init__(self, stream):
        self._stream = stream
        self._parts = []

    def write(self, text):
        self._parts.append(text)
        return self._stream.write(text)

    def flush(self):
        self._stream.flush()

    def captured(self):
        return "".join(self._parts)


def run(args):
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    for key in ("harness_arn", "gateway_arn", "table_name"):
        if key not in config:
            sys.exit(f"{key} missing from {args.config} — run setup_gateway.py "
                     "and create_harness.py first.")
    region = config["region"]

    guard = None
    if args.guardrail:
        from guardrail import check_input, load_guardrail
        ids = load_guardrail(config)
        if ids is None:
            sys.exit("No guardrail in config — run setup_guardrail.py first.")
        runtime = boto3.client("bedrock-runtime", region_name=region)
        guard = (runtime, ids, check_input)

    rt = boto3.client(
        "bedrock-agentcore",
        region_name=region,
        config=Config(read_timeout=300, retries={"max_attempts": 1}),
    )
    session_id = f"{uuid.uuid4()}-multiturn"
    transcript = [f"session {session_id}"]
    failures = []
    final_reply = ""

    print(f"Session {session_id}\n")
    for index, turn in enumerate(SCRIPT):
        is_last = index == len(SCRIPT) - 1
        print(f"you> {turn['text']}")
        transcript.append(f"you> {turn['text']}")

        if guard:
            runtime, (gid, version), check_input = guard
            result = check_input(runtime, gid, version, turn["text"])
            if result.blocked:
                failures.append(f"turn {index + 1}: guardrail blocked a legitimate "
                                f"message ({result.message})")
                transcript.append(f"[guardrail blocked] {result.message}")
                break

        print("bot> ", end="", flush=True)
        tee = Tee(sys.stdout)
        with contextlib.redirect_stdout(tee):
            reply = invoke(rt, config, session_id, turn["text"])
        tool_calls = tee.captured().count(TOOL_CALL_MARKER)
        transcript.extend(line for line in tee.captured().splitlines()
                          if line.startswith(TOOL_CALL_MARKER))
        transcript.append(f"bot> {reply}")
        print()

        if not is_last and tool_calls:
            failures.append(f"turn {index + 1}: tool called before all fields were given")
        if is_last:
            final_reply = reply
            if tool_calls != 1:
                failures.append(f"final turn: expected exactly 1 tool call, saw {tool_calls}")

    ticket_id = extract_ticket_id(final_reply)
    if not failures and not ticket_id:
        failures.append("final reply contains no ticket ID")

    if ticket_id:
        table = boto3.resource("dynamodb", region_name=region).Table(config["table_name"])
        item = table.get_item(Key={"ticketId": ticket_id}, ConsistentRead=True).get("Item")
        if not item:
            failures.append(f"ticket {ticket_id} not found in {config['table_name']}")
        else:
            transcript.append("stored ticket: " + json.dumps(item, default=str, sort_keys=True))
            for turn in SCRIPT:
                if not field_matches(item.get(turn["field"]), turn["keywords"]):
                    failures.append(f"stored {turn['field']} {item.get(turn['field'])!r} "
                                    f"lacks keywords {turn['keywords']}")

    verdict = "PASS" if not failures else "FAIL"
    transcript.append(f"ticket id: {ticket_id or '-'}")
    transcript.append(f"result: {verdict}")
    transcript.extend(f"  - {f}" for f in failures)

    print(f"ticket id: {ticket_id or '-'}")
    print(verdict)
    for failure in failures:
        print(f"  - {failure}")

    if args.transcript_out:
        out = Path(args.transcript_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(transcript) + "\n", encoding="utf-8")
        print(f"Transcript saved to {out}")
    return 0 if not failures else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="agentcore_config.json")
    parser.add_argument("--guardrail", action="store_true",
                        help="Check each scripted message with the guardrail first "
                             "(fails if a legitimate message is blocked).")
    parser.add_argument("--transcript-out", default=None,
                        help="Write the conversation and the result to this file.")
    sys.exit(run(parser.parse_args()))


if __name__ == "__main__":
    main()
