#!/usr/bin/env python3
"""Run a Bedrock Evaluations LLM-as-a-judge job on the generated dataset.

    python run_bedrock_eval.py --wait --scores-out ../evidence/eval_scores.md

Steps:
  1. Read the outputs of the testing stack (bucket and evaluation role).
  2. Upload output_eval_dataset.jsonl to s3://<bucket>/datasets/<job-name>.jsonl.
  3. Create the evaluation job: metric Builtin.Correctness, evaluator model
     amazon.nova-pro-v1:0, precomputed responses from "my-support-chatbot"
     (bring your own inference). Results go to s3://<bucket>/results/.
  4. With --wait: poll until the job finishes, download the result JSONL
     files and print a per-record score table and the mean.

Deploy the testing stack first:

    aws cloudformation deploy --template-file cloudformation-testing.yaml \\
      --stack-name bug-report-testing-stack --capabilities CAPABILITY_NAMED_IAM --region us-east-1
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3

from mask_evidence import mask_account_ids

REGION = "us-east-1"
METRIC = "Builtin.Correctness"
EVALUATOR_MODEL = "amazon.nova-pro-v1:0"
INFERENCE_SOURCE = "my-support-chatbot"
TERMINAL_STATUSES = {"Completed", "Failed", "Stopped"}
PROMPT_WIDTH = 70


def extract_scores(record):
    """Return the Builtin.Correctness score found anywhere in a result record.

    Accepts both {"metricName": "Builtin.Correctness", "result": 1.0} entries
    and {"Builtin.Correctness": 1.0} keys. Returns None when absent.
    """
    if isinstance(record, dict):
        if record.get("metricName") == METRIC:
            for key in ("result", "score", "value"):
                value = record.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return float(value)
        value = record.get(METRIC)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        children = record.values()
    elif isinstance(record, list):
        children = record
    else:
        return None
    for child in children:
        score = extract_scores(child)
        if score is not None:
            return score
    return None


def _prompt_of(record):
    """Best-effort prompt text from a result record."""
    for container in (record.get("inputRecord"), record):
        if isinstance(container, dict) and isinstance(container.get("prompt"), str):
            return container["prompt"]
    return ""


def score_table(rows):
    """Return (markdown_table, mean) for [(prompt, score_or_None)]."""
    lines = ["| # | prompt | score |", "|---|--------|-------|"]
    for index, (prompt, score) in enumerate(rows, 1):
        text = " ".join(prompt.split()).replace("|", "\\|")
        if len(text) > PROMPT_WIDTH:
            text = text[:PROMPT_WIDTH - 1] + "…"
        lines.append(f"| {index} | {text} | {'n/a' if score is None else f'{score:.2f}'} |")
    scored = [s for _, s in rows if s is not None]
    mean = sum(scored) / len(scored) if scored else None
    return "\n".join(lines), mean


def stack_outputs(cfn, stack_name):
    stack = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}


def download_results(s3, bucket, prefix):
    """Return every JSON record in the .jsonl files under prefix."""
    records = []
    paginator = s3.get_paginator("list_objects_v2")
    keys = sorted(obj["Key"] for page in paginator.paginate(Bucket=bucket, Prefix=prefix)
                  for obj in page.get("Contents", []) if obj["Key"].endswith(".jsonl"))
    for key in keys:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")
        records.extend(json.loads(line) for line in body.splitlines() if line.strip())
    return records


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="output_eval_dataset.jsonl")
    parser.add_argument("--job-name", default=f"support-chatbot-eval-run-{stamp}",
                        help="Lowercase letters, digits and hyphens.")
    parser.add_argument("--stack-name", default="bug-report-testing-stack")
    parser.add_argument("--task-type", default="General",
                        help="datasetMetricConfigs taskType (default: General).")
    parser.add_argument("--wait", action="store_true",
                        help="Poll until the job finishes and print per-record scores.")
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--scores-out", default=None,
                        help="Write the per-record score table (markdown) here; needs --wait.")
    args = parser.parse_args()

    dataset = Path(args.dataset)
    if not dataset.exists():
        sys.exit(f"{dataset} not found — run generate-eval-dataset.py first.")
    lines = [l for l in dataset.read_text(encoding="utf-8").splitlines() if l.strip()]
    errors = sum("[HARNESS_ERROR]" in l for l in lines)
    if errors:
        print(f"WARNING: {errors} of {len(lines)} records contain [HARNESS_ERROR].")

    cfn = boto3.client("cloudformation", region_name=REGION)
    outputs = stack_outputs(cfn, args.stack_name)
    bucket = outputs["EvalDatasetBucketName"]
    role_arn = outputs["BedrockEvalRoleArn"]

    s3 = boto3.client("s3", region_name=REGION)
    dataset_key = f"datasets/{args.job_name}.jsonl"
    s3.upload_file(str(dataset), bucket, dataset_key)
    dataset_uri = f"s3://{bucket}/{dataset_key}"
    output_uri = f"s3://{bucket}/results/"
    print(f"Uploaded {len(lines)} records to {dataset_uri}")

    bedrock = boto3.client("bedrock", region_name=REGION)
    job = bedrock.create_evaluation_job(
        jobName=args.job_name,
        roleArn=role_arn,
        applicationType="ModelEvaluation",
        evaluationConfig={
            "automated": {
                "datasetMetricConfigs": [{
                    "taskType": args.task_type,
                    "dataset": {
                        "name": "SupportChatbotDataset",
                        "datasetLocation": {"s3Uri": dataset_uri},
                    },
                    "metricNames": [METRIC],
                }],
                "evaluatorModelConfig": {
                    "bedrockEvaluatorModels": [{"modelIdentifier": EVALUATOR_MODEL}],
                },
            }
        },
        inferenceConfig={
            "models": [{
                "precomputedInferenceSource": {"inferenceSourceIdentifier": INFERENCE_SOURCE},
            }]
        },
        outputDataConfig={"s3Uri": output_uri},
    )
    job_arn = job["jobArn"]
    print(f"Created evaluation job {args.job_name}\n  arn: {job_arn}")
    if not args.wait:
        print("Re-run with --wait (or check the Bedrock console) for the results.")
        return 0

    while True:
        status = bedrock.get_evaluation_job(jobIdentifier=job_arn)["status"]
        print(f"  status: {status}")
        if status in TERMINAL_STATUSES:
            break
        time.sleep(args.poll_seconds)
    if status != "Completed":
        details = bedrock.get_evaluation_job(jobIdentifier=job_arn).get("failureMessages", [])
        sys.exit(f"Evaluation job ended with status {status}: {details}")

    records = download_results(s3, bucket, f"results/{args.job_name}/")
    if not records:
        sys.exit(f"No result files found under {output_uri}{args.job_name}/")
    rows = [(_prompt_of(r), extract_scores(r)) for r in records]
    table, mean = score_table(rows)
    mean_text = "n/a" if mean is None else f"{mean:.3f}"
    report = (
        f"# Evaluation scores\n\n"
        f"- Job: `{args.job_name}`\n"
        f"- ARN: `{mask_account_ids(job_arn)}`\n"
        f"- Metric: `{METRIC}` (evaluator `{EVALUATOR_MODEL}`)\n"
        f"- Records: {len(rows)}; mean score: {mean_text}\n\n"
        f"{table}\n"
    )
    print("\n" + report)
    if args.scores_out:
        out = Path(args.scores_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"Saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
