#!/usr/bin/env python3
"""Copy local AWS state files into the evidence folder with the account ID masked.

    python mask_evidence.py [--out-dir ../evidence]

Copies agentcore_config.json and output_eval_dataset.jsonl (if they exist)
and replaces every 12-digit AWS account ID with ************. UUIDs,
timestamps and other numbers are left alone. The raw files stay git-ignored;
commit only the masked copies.
"""

import argparse
import re
import sys
from pathlib import Path

MASK = "************"
FILES = ("agentcore_config.json", "output_eval_dataset.jsonl")

# A UUID is matched first so that its last group (12 hex characters, which
# can be all digits) is kept. Otherwise any run of exactly 12 digits is an
# account ID: inside ARNs (":123456789012:"), bucket names ("-123456789012")
# or on its own.
_TOKEN = re.compile(
    r"(?P<uuid>\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b)"
    r"|(?<!\d)(?P<account>\d{12})(?!\d)"
)


def mask_account_ids(text):
    """Replace 12-digit AWS account IDs in text with asterisks."""
    return _TOKEN.sub(lambda m: m.group("uuid") or MASK, text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", default="../evidence",
                        help="Where to write the masked copies.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name in FILES:
        source = Path(name)
        if not source.exists():
            print(f"skip    {name} (not found)")
            continue
        target = out_dir / name
        target.write_text(mask_account_ids(source.read_text(encoding="utf-8")),
                          encoding="utf-8")
        print(f"masked  {name} -> {target}")
        copied += 1
    if not copied:
        print("Nothing to copy — run the setup and dataset scripts first.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
