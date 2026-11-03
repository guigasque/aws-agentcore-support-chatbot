"""Tests for the offline helpers in multiturn_bug_test.py."""

import multiturn_bug_test as mt

TICKET = "3f2b8c1e-9a4d-4e7b-8c21-5d6e7f8a9b0c"


def test_extract_ticket_id_finds_uuid4():
    text = f"Thanks! Your ticket ID is {TICKET}. Our team will look into it."
    assert mt.extract_ticket_id(text) == TICKET


def test_extract_ticket_id_case_insensitive_and_bold():
    assert mt.extract_ticket_id(f"Ticket: **{TICKET.upper()}**") == TICKET.upper()


def test_extract_ticket_id_none_when_absent():
    assert mt.extract_ticket_id("Which browser and operating system were you using?") is None
    assert mt.extract_ticket_id("") is None


def test_extract_ticket_id_ignores_non_v4_uuid():
    # Version nibble 1, not 4.
    assert mt.extract_ticket_id("id 3f2b8c1e-9a4d-1e7b-8c21-5d6e7f8a9b0c") is None


def test_field_matches_requires_all_keywords_case_insensitive():
    value = "The CHECKOUT page crashes when I click Pay"
    assert mt.field_matches(value, ["checkout", "pay"])
    assert not mt.field_matches(value, ["checkout", "login"])


def test_field_matches_rejects_empty_value():
    assert not mt.field_matches("", ["checkout"])
    assert not mt.field_matches(None, ["checkout"])


def test_script_covers_every_field():
    assert mt.SCRIPT, "the scripted conversation must not be empty"
    provided = {turn["field"] for turn in mt.SCRIPT}
    assert provided == {"description", "stepsToReproduce", "environment"}
    for turn in mt.SCRIPT:
        assert turn["text"].strip()
        assert turn["keywords"]
        # Each turn's own text must contain its keywords, otherwise the
        # DynamoDB assertion could never pass.
        assert mt.field_matches(turn["text"], turn["keywords"])


def test_tee_captures_and_forwards():
    import io

    sink = io.StringIO()
    tee = mt.Tee(sink)
    tee.write("[tool call] x\n")
    tee.flush()
    assert sink.getvalue() == "[tool call] x\n"
    assert tee.captured() == "[tool call] x\n"
