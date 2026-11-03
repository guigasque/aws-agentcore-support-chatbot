#!/usr/bin/env python3
"""Offline quality gate for the prompt, the FAQ and the test suite.

    python validate_offline.py

Needs no AWS access and only the standard library. Prints one PASS/FAIL line
per check and exits 0 only when every check passes. Run it before every
commit that touches system_prompt.txt, online_shop_faq.md or
harness-tests.json.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

FAQ_PLACEHOLDER = "{{FAQ}}"
ROUTE_NAMES = ("BUG_REPORT", "PLATFORM_QUESTION", "OTHER")
PHONE = "+1 (800) 555-0199"
TOOL_NAME = "bugreports___create_bug_report"
MAX_RENDERED_CHARS = 32000

TEST_FIELDS = ("id", "route", "prompt", "expected")
ID_PATTERN = re.compile(r"^[a-z]+(_[a-z0-9]+)+$")
MIN_EXPECTED_CHARS = 20
MIN_TOTAL_TESTS = 18
# Minimum number of tests per route tag (FR-019).
MIN_ROUTE_COUNTS = {
    "bug": 3,
    "faq": 4,
    "faq_miss": 2,
    "other": 3,
    "edge": 3,
    "injection": 2,
    "faq_ext": 1,
}
# The first segment of a test id must match its route tag.
ROUTE_ID_PREFIX = {
    "bug": "bug",
    "faq": "faq",
    "faq_miss": "faqmiss",
    "faq_ext": "ext",
    "other": "other",
    "edge": "edge",
    "injection": "inj",
}
NEW_FAQ_ENTRIES = ("33)", "34)")


# ---------------------------------------------------------------- prompt


def prompt_checks(text, faq):
    """Return [(check_name, error_or_None)] for checks S1-S6."""
    results = []

    count = text.count(FAQ_PLACEHOLDER)
    faq_block = re.search(r"<faq>(.*?)</faq>", text, re.DOTALL)
    if count != 1:
        error = f"S1: {FAQ_PLACEHOLDER} must appear exactly once (found {count})"
    elif not faq_block or FAQ_PLACEHOLDER not in faq_block.group(1):
        error = f"S1: {FAQ_PLACEHOLDER} must be inside a <faq> ... </faq> block"
    else:
        error = None
    results.append(("S1 FAQ placeholder", error))

    comment_lines = [n for n, line in enumerate(text.splitlines(), 1)
                     if line.lstrip().startswith("#")]
    results.append(("S2 no starter comments", None if not comment_lines else
                     f"S2: remove comment lines starting with '#' (lines {comment_lines[:5]})"))

    missing = [name for name in ROUTE_NAMES if name not in text]
    results.append(("S3 route names", None if not missing else
                    f"S3: missing route name(s): {', '.join(missing)}"))

    results.append(("S4 support phone line", None if PHONE in text else
                    f"S4: missing support phone line {PHONE}"))

    results.append(("S5 tool name", None if TOOL_NAME in text else
                    f"S5: missing tool name {TOOL_NAME}"))

    rendered = len(text.replace(FAQ_PLACEHOLDER, faq))
    results.append(("S6 rendered size", None if rendered <= MAX_RENDERED_CHARS else
                    f"S6: rendered prompt is {rendered} characters "
                    f"(limit {MAX_RENDERED_CHARS})"))
    return results


def check_prompt(text, faq):
    """Return the list of error messages for the system prompt."""
    return [error for _, error in prompt_checks(text, faq) if error]


# ---------------------------------------------------------------- test suite


def _check_test_case(index, test):
    errors = []
    where = f"tests[{index}]"
    if not isinstance(test, dict):
        return [f"{where}: must be an object"]
    where = f"tests[{index}] ({test.get('id', '?')})"

    missing = [f for f in TEST_FIELDS if f not in test]
    extra = sorted(set(test) - set(TEST_FIELDS))
    if missing:
        errors.append(f"{where}: missing field(s): {', '.join(missing)}")
    if extra:
        errors.append(f"{where}: unexpected field(s): {', '.join(extra)}")

    for field in TEST_FIELDS:
        if field in test and not isinstance(test[field], str):
            errors.append(f"{where}: '{field}' must be a string")
    if errors:
        return errors

    if not ID_PATTERN.match(test["id"]):
        errors.append(f"{where}: id must match {ID_PATTERN.pattern}")
    if test["route"] not in MIN_ROUTE_COUNTS:
        errors.append(f"{where}: unknown route '{test['route']}' "
                      f"(allowed: {', '.join(MIN_ROUTE_COUNTS)})")
    elif test["id"].split("_")[0] != ROUTE_ID_PREFIX[test["route"]]:
        errors.append(f"{where}: id prefix must be '{ROUTE_ID_PREFIX[test['route']]}_' "
                      f"for route '{test['route']}'")
    if not test["prompt"].strip():
        errors.append(f"{where}: prompt must not be empty")
    if len(test["expected"]) < MIN_EXPECTED_CHARS:
        errors.append(f"{where}: expected must be at least {MIN_EXPECTED_CHARS} characters")
    return errors


def check_tests(obj):
    """Return the list of error messages for a parsed harness-tests.json."""
    if not isinstance(obj, dict) or not isinstance(obj.get("tests"), list):
        return ["suite must be an object with a 'tests' array"]
    errors = []
    extra = sorted(set(obj) - {"tests"})
    if extra:
        errors.append(f"suite: unexpected top-level key(s): {', '.join(extra)}")

    tests = obj["tests"]
    for index, test in enumerate(tests):
        errors.extend(_check_test_case(index, test))

    ids = Counter(t.get("id") for t in tests if isinstance(t, dict))
    duplicates = sorted(str(i) for i, n in ids.items() if n > 1)
    if duplicates:
        errors.append(f"duplicate id(s): {', '.join(duplicates)}")

    routes = Counter(t.get("route") for t in tests if isinstance(t, dict))
    for route, minimum in MIN_ROUTE_COUNTS.items():
        if routes[route] < minimum:
            errors.append(f"route '{route}' needs at least {minimum} test(s) "
                          f"(found {routes[route]})")
    if len(tests) < MIN_TOTAL_TESTS:
        errors.append(f"suite needs at least {MIN_TOTAL_TESTS} tests (found {len(tests)})")
    return errors


# ---------------------------------------------------------------- FAQ


def check_faq(text):
    """Return the list of error messages for the FAQ file."""
    starts = {line.strip().split(" ", 1)[0] for line in text.splitlines() if line.strip()}
    return [f"FAQ: missing entry {entry}" for entry in NEW_FAQ_ENTRIES if entry not in starts]


# ---------------------------------------------------------------- CLI


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, f"cannot read {path}: {exc}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt-file", default="system_prompt.txt")
    parser.add_argument("--faq-file", default="online_shop_faq.md")
    parser.add_argument("--tests-json", default="harness-tests.json")
    args = parser.parse_args(argv)

    results = []  # (name, [errors])

    faq, faq_error = _read(args.faq_file)
    prompt, prompt_error = _read(args.prompt_file)
    if prompt_error or faq_error:
        results.append(("prompt", [e for e in (prompt_error, faq_error) if e]))
    else:
        results.extend((name, [error] if error else [])
                       for name, error in prompt_checks(prompt, faq))

    results.append(("FAQ entries 33-34", [faq_error] if faq_error else check_faq(faq)))

    raw, tests_error = _read(args.tests_json)
    if tests_error:
        results.append(("test suite", [tests_error]))
    else:
        try:
            suite = json.loads(raw)
        except json.JSONDecodeError as exc:
            results.append(("test suite", [f"{args.tests_json} is not valid JSON: {exc}"]))
        else:
            results.append(("test suite", check_tests(suite)))

    failed = False
    for name, errors in results:
        print(f"{'FAIL' if errors else 'PASS'}  {name}")
        for error in errors:
            print(f"        - {error}")
        failed = failed or bool(errors)
    print("\nAll offline checks passed." if not failed else "\nOffline checks FAILED.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
