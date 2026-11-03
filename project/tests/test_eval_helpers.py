"""Tests for mask_evidence.mask_account_ids and run_bedrock_eval.extract_scores."""

import json

import pytest

import mask_evidence
import run_bedrock_eval

ACCOUNT = "123456789012"
MASK = "************"


@pytest.mark.parametrize("text, expected", [
    (f"arn:aws:iam::{ACCOUNT}:role/bedrock-eval-role", f"arn:aws:iam::{MASK}:role/bedrock-eval-role"),
    (f"arn:aws:bedrock-agentcore:us-east-1:{ACCOUNT}:gateway/gw-1",
     f"arn:aws:bedrock-agentcore:us-east-1:{MASK}:gateway/gw-1"),
    (f"s3://udacity-agentic-engineer-c1-eval-{ACCOUNT}/datasets/x.jsonl",
     f"s3://udacity-agentic-engineer-c1-eval-{MASK}/datasets/x.jsonl"),
    (f"account {ACCOUNT}", f"account {MASK}"),
    (f'{{"account": "{ACCOUNT}"}}', f'{{"account": "{MASK}"}}'),
])
def test_masks_account_ids(text, expected):
    assert mask_evidence.mask_account_ids(text) == expected


@pytest.mark.parametrize("text", [
    "3f2b8c1e-9a4d-4e7b-8c21-123456789012",   # UUID whose last group is all digits
    "2026-10-19T12:34:56.123456+00:00",         # ISO timestamp
    "1791234567890",                            # 13-digit epoch milliseconds
    "12345678901",                              # 11 digits
])
def test_leaves_other_numbers_alone(text):
    assert mask_evidence.mask_account_ids(text) == text


def test_masks_inside_uuid_free_text_with_uuid_present():
    text = f"ticket 3f2b8c1e-9a4d-4e7b-8c21-5d6e7f8a9b0c in account {ACCOUNT}"
    assert mask_evidence.mask_account_ids(text) == (
        f"ticket 3f2b8c1e-9a4d-4e7b-8c21-5d6e7f8a9b0c in account {MASK}")


def test_cli_copies_and_masks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "agentcore_config.json").write_text(
        json.dumps({"harness_arn": f"arn:aws:x:us-east-1:{ACCOUNT}:harness/h"}), encoding="utf-8")
    out = tmp_path / "evidence"
    assert mask_evidence.main(["--out-dir", str(out)]) == 0
    copied = (out / "agentcore_config.json").read_text(encoding="utf-8")
    assert ACCOUNT not in copied and MASK in copied
    assert not (out / "output_eval_dataset.jsonl").exists()


# ---------------------------------------------------------------- extract_scores


def test_extract_scores_bedrock_shape():
    record = {
        "automatedEvaluationResult": {
            "scores": [
                {"metricName": "Builtin.Helpfulness", "result": 0.3},
                {"metricName": "Builtin.Correctness", "result": 1.0,
                 "evaluatorDetails": [{"modelIdentifier": "amazon.nova-pro-v1:0"}]},
            ]
        },
        "inputRecord": {"prompt": "hi"},
    }
    assert run_bedrock_eval.extract_scores(record) == 1.0


def test_extract_scores_deeply_nested_and_key_form():
    record = {"a": [{"b": {"c": [{"metricName": "Builtin.Correctness", "score": 0.5}]}}]}
    assert run_bedrock_eval.extract_scores(record) == 0.5
    assert run_bedrock_eval.extract_scores({"x": {"Builtin.Correctness": 0}}) == 0.0


def test_extract_scores_absent():
    assert run_bedrock_eval.extract_scores({"automatedEvaluationResult": {"scores": []}}) is None
    assert run_bedrock_eval.extract_scores({}) is None
    record = {"scores": [{"metricName": "Builtin.Helpfulness", "result": 1.0}]}
    assert run_bedrock_eval.extract_scores(record) is None


def test_extract_scores_ignores_metric_without_value():
    record = {"scores": [{"metricName": "Builtin.Correctness", "result": None}]}
    assert run_bedrock_eval.extract_scores(record) is None


def test_score_table_and_mean():
    rows = [("How long do I have to return an item?", 1.0), ("hi", 0.5), ("x" * 200, None)]
    table, mean = run_bedrock_eval.score_table(rows)
    assert mean == pytest.approx(0.75)
    assert "| 1 |" in table and "| 3 |" in table
    assert "n/a" in table
    assert "x" * 200 not in table  # prompts are truncated
