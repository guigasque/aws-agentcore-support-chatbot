#!/usr/bin/env python3
"""Record the deployed guardrail in agentcore_config.json.

Run this after deploying cloudformation-guardrail.yaml:

    aws cloudformation deploy --template-file cloudformation-guardrail.yaml \\
      --stack-name bug-report-guardrail-stack --region us-east-1
    python setup_guardrail.py

It reads the stack outputs GuardrailId and GuardrailVersion and merges them
into the config as guardrail_id and guardrail_version. Other keys are kept.
Then use the guardrail with:  python chat.py --guardrail
"""

import argparse
import json
import sys
from pathlib import Path

import boto3

REGION = "us-east-1"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stack-name", default="bug-report-guardrail-stack",
                        help="Name of the deployed cloudformation-guardrail.yaml stack.")
    parser.add_argument("--config", default="agentcore_config.json",
                        help="Config file written by setup_gateway.py.")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"{args.config} not found — run setup_gateway.py first.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    region = config.get("region", REGION)

    cfn = boto3.client("cloudformation", region_name=region)
    stack = cfn.describe_stacks(StackName=args.stack_name)["Stacks"][0]
    outputs = {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}
    missing = [k for k in ("GuardrailId", "GuardrailVersion") if k not in outputs]
    if missing:
        sys.exit(f"Stack {args.stack_name} has no output(s) {', '.join(missing)} "
                 f"(status {stack.get('StackStatus')}).")

    config["guardrail_id"] = outputs["GuardrailId"]
    config["guardrail_version"] = outputs["GuardrailVersion"]
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    print(f"guardrail id:      {config['guardrail_id']}")
    print(f"guardrail version: {config['guardrail_version']}")
    print(f"Saved to {args.config}. Try it with:  python chat.py --guardrail")


if __name__ == "__main__":
    main()
