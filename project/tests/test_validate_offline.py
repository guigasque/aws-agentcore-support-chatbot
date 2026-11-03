"""Tests for validate_offline.py (contracts/cli.md, contracts/system-prompt.md S1-S6)."""

import copy
import json

import pytest

import validate_offline as vo

FAQ = "Online Shop FAQ\n\n33) What is the customer support phone number?\n+1 (800) 555-0199\n\n34) Do you sell gift cards?\nNo.\n"

GOOD_PROMPT = """<role>You are the support assistant.</role>
<routing>Pick exactly one of BUG_REPORT, PLATFORM_QUESTION or OTHER.</routing>
<bug_report_procedure>Call bugreports___create_bug_report when all fields are known.</bug_report_procedure>
<handoff>Call +1 (800) 555-0199, Monday–Friday.</handoff>
<faq>
{{FAQ}}
</faq>
"""


def _test(id_, route, prompt="A customer message", expected="A long enough expected description."):
    return {"id": id_, "route": route, "prompt": prompt, "expected": expected}


def good_suite():
    tests = (
        [_test(f"bug_case_{i}", "bug") for i in range(3)]
        + [_test(f"faq_case_{i}", "faq") for i in range(4)]
        + [_test(f"faqmiss_case_{i}", "faq_miss") for i in range(2)]
        + [_test(f"other_case_{i}", "other") for i in range(3)]
        + [_test(f"edge_case_{i}", "edge") for i in range(3)]
        + [_test(f"inj_case_{i}", "injection") for i in range(2)]
        + [_test("ext_case_one", "faq_ext")]
    )
    return {"tests": tests}


# ---------------------------------------------------------------- prompt


def test_good_prompt_passes():
    assert vo.check_prompt(GOOD_PROMPT, FAQ) == []


def test_missing_placeholder_fails():
    errors = vo.check_prompt(GOOD_PROMPT.replace("{{FAQ}}", ""), FAQ)
    assert any("S1" in e for e in errors)


def test_placeholder_twice_fails():
    errors = vo.check_prompt(GOOD_PROMPT + "\n{{FAQ}}\n", FAQ)
    assert any("S1" in e for e in errors)


def test_placeholder_outside_faq_block_fails():
    text = GOOD_PROMPT.replace("<faq>\n{{FAQ}}\n</faq>", "{{FAQ}}")
    errors = vo.check_prompt(text, FAQ)
    assert any("S1" in e for e in errors)


@pytest.mark.parametrize("comment", ["# Write your system prompt in this file.", "   # indented comment"])
def test_comment_lines_fail(comment):
    errors = vo.check_prompt(comment + "\n" + GOOD_PROMPT, FAQ)
    assert any("S2" in e for e in errors)


@pytest.mark.parametrize("route", ["BUG_REPORT", "PLATFORM_QUESTION", "OTHER"])
def test_missing_route_fails(route):
    errors = vo.check_prompt(GOOD_PROMPT.replace(route, "SOMETHING"), FAQ)
    assert any("S3" in e and route in e for e in errors)


def test_missing_phone_fails():
    errors = vo.check_prompt(GOOD_PROMPT.replace("+1 (800) 555-0199", "the phone line"), FAQ)
    assert any("S4" in e for e in errors)


def test_missing_tool_name_fails():
    errors = vo.check_prompt(GOOD_PROMPT.replace("bugreports___create_bug_report", "the tool"), FAQ)
    assert any("S5" in e for e in errors)


def test_rendered_prompt_too_long_fails():
    errors = vo.check_prompt(GOOD_PROMPT, FAQ + "x" * vo.MAX_RENDERED_CHARS)
    assert any("S6" in e for e in errors)


# ---------------------------------------------------------------- test suite


def test_good_suite_passes():
    assert vo.check_tests(good_suite()) == []


def test_suite_must_be_object_with_tests():
    assert vo.check_tests([]) != []
    assert vo.check_tests({"tests": [], "extra": 1}) != []


def test_duplicate_ids_fail():
    suite = good_suite()
    suite["tests"][1]["id"] = suite["tests"][0]["id"]
    assert any("duplicate" in e for e in vo.check_tests(suite))


@pytest.mark.parametrize("bad_id", ["Bug_case", "bug", "bug-case", "bug_", "bug case"])
def test_bad_id_pattern_fails(bad_id):
    suite = good_suite()
    suite["tests"][0]["id"] = bad_id
    assert vo.check_tests(suite) != []


def test_unknown_route_fails():
    suite = good_suite()
    suite["tests"][0]["route"] = "billing"
    assert vo.check_tests(suite) != []


@pytest.mark.parametrize("field", ["id", "route", "prompt", "expected"])
def test_missing_field_fails(field):
    suite = good_suite()
    del suite["tests"][0][field]
    assert vo.check_tests(suite) != []


def test_extra_field_fails():
    suite = good_suite()
    suite["tests"][0]["notes"] = "x"
    assert vo.check_tests(suite) != []


def test_empty_prompt_fails():
    suite = good_suite()
    suite["tests"][0]["prompt"] = ""
    assert vo.check_tests(suite) != []


def test_short_expected_fails():
    suite = good_suite()
    suite["tests"][0]["expected"] = "too short"
    assert vo.check_tests(suite) != []


def test_non_string_values_fail():
    suite = good_suite()
    suite["tests"][0]["prompt"] = 42
    assert vo.check_tests(suite) != []


@pytest.mark.parametrize("route", ["bug", "faq", "faq_miss", "other", "edge", "injection", "faq_ext"])
def test_route_minimum_counts(route):
    suite = good_suite()
    suite["tests"] = [t for t in suite["tests"] if t["route"] != route]
    errors = vo.check_tests(suite)
    assert any(route in e for e in errors)


def test_total_minimum():
    suite = good_suite()
    assert len(suite["tests"]) == 18
    suite["tests"].append(_test("bug_case_extra", "bug"))
    assert vo.check_tests(suite) == []
    smaller = copy.deepcopy(suite)
    smaller["tests"] = smaller["tests"][:17]
    assert vo.check_tests(smaller) != []


@pytest.mark.parametrize("id_, route", [
    ("faq_case_x", "bug"),
    ("bug_case_x", "faq"),
    ("faq_case_x", "faq_miss"),
    ("faq_case_x", "faq_ext"),
    ("other_case_x", "injection"),
])
def test_prefix_must_match_route(id_, route):
    suite = good_suite()
    suite["tests"].append(_test(id_, route))
    assert any("prefix" in e for e in vo.check_tests(suite))


# ---------------------------------------------------------------- FAQ


def test_faq_with_new_entries_passes():
    assert vo.check_faq(FAQ) == []


@pytest.mark.parametrize("entry", ["33)", "34)"])
def test_faq_missing_entry_fails(entry):
    text = FAQ.replace(entry, "99)")
    assert any(entry in e for e in vo.check_faq(text))


# ---------------------------------------------------------------- CLI


def test_cli_exit_codes(tmp_path, capsys):
    (tmp_path / "p.txt").write_text(GOOD_PROMPT, encoding="utf-8")
    (tmp_path / "f.md").write_text(FAQ, encoding="utf-8")
    (tmp_path / "t.json").write_text(json.dumps(good_suite()), encoding="utf-8")
    args = ["--prompt-file", str(tmp_path / "p.txt"), "--faq-file", str(tmp_path / "f.md"),
            "--tests-json", str(tmp_path / "t.json")]
    assert vo.main(args) == 0
    assert "FAIL" not in capsys.readouterr().out

    (tmp_path / "t.json").write_text("{not json", encoding="utf-8")
    assert vo.main(args) == 1
    assert "FAIL" in capsys.readouterr().out


def test_cli_missing_tests_file_fails(tmp_path):
    (tmp_path / "p.txt").write_text(GOOD_PROMPT, encoding="utf-8")
    (tmp_path / "f.md").write_text(FAQ, encoding="utf-8")
    args = ["--prompt-file", str(tmp_path / "p.txt"), "--faq-file", str(tmp_path / "f.md"),
            "--tests-json", str(tmp_path / "missing.json")]
    assert vo.main(args) == 1


def test_repository_files_pass(starter_dir):
    """The committed prompt, FAQ and suite pass every gate."""
    args = ["--prompt-file", str(starter_dir / "system_prompt.txt"),
            "--faq-file", str(starter_dir / "online_shop_faq.md"),
            "--tests-json", str(starter_dir / "harness-tests.json")]
    assert vo.main(args) == 0
