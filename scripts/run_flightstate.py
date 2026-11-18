"""Noninteractive FlightState orchestration for flightstate_pipeline 3.2.0.

Install in data_project/scripts. Run as: python -m scripts.run_flightstate
Default job file: config/flightstate_jobs.json; default mode: database dry run.
Jobs JSON: {"jobs": [{"input": "data/extracted/example.log",
                     "run_config": "config/flightstate_run.json"}]}
Each job is one complete extracted file with confirmed run metadata.
This runner does not extract archives, watch directories, or infer metadata.
The existing loader owns transactional writes and duplicate prevention.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4


def resolve_path(root, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Job paths must be nonempty strings.")
    path = Path(value)
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def read_jobs(pipeline, path):
    plan = pipeline.parse_json(path.read_text(encoding="utf-8-sig"))
    if not isinstance(plan, dict) or set(plan) != {"jobs"}:
        raise ValueError('Jobs file must contain exactly one key: "jobs".')
    if not isinstance(plan["jobs"], list) or not plan["jobs"]:
        raise ValueError("jobs must be a nonempty list.")
    jobs, seen = [], set()
    for job in plan["jobs"]:
        if not isinstance(job, dict) or set(job) != {"input", "run_config"}:
            raise ValueError("Each job needs exactly input and run_config.")
        source = resolve_path(pipeline.ROOT, job["input"])
        config = resolve_path(pipeline.ROOT, job["run_config"])
        if source in seen:
            raise ValueError(f"Duplicate input in jobs file: {source}")
        seen.add(source)
        if not source.is_file():
            raise ValueError(f"Input file not found: {source}")
        cfg = pipeline.validate_config(pipeline.parse_json(
            config.read_text(encoding="utf-8-sig")
        ))
        jobs.append((source, cfg))
    return jobs


def execute(pipeline, jobs, directories, commit=False, batch_size=500):
    """Stop on first failure. Earlier successful jobs remain committed."""
    reports = []
    for source, config in jobs:
        item = {"input": str(source), "status": "STARTED"}
        reports.append(item)
        db = None
        try:
            print(f"Staging {source.name}", file=sys.stderr, flush=True)
            manifest_path, manifest, reused = pipeline.stage_file(
                source, directories["staged"], config
            )
            item.update(manifest=str(manifest_path), records=manifest["records"],
                        reused=reused, status=manifest["status"])
            if manifest["status"] != "READY":
                item["first_error"] = manifest.get("first_error")
                return reports, 2
            url = os.getenv("DATABASE_URL")
            if not url:
                raise ValueError("Set DATABASE_URL in the project .env file.")
            db = pipeline.Database(url)
            print("Validating database and staged records", file=sys.stderr, flush=True)
            validation = pipeline.load_bundle(db, manifest_path, commit=False,
                batch=batch_size, receipt_directory=directories["processed"])
            item["validation"] = validation
            if validation["status"] != "VALIDATED":
                item["status"] = validation["status"]
                return reports, 2
            if commit:
                print("Loading into rrdata", file=sys.stderr, flush=True)
                result = pipeline.load_bundle(db, manifest_path, commit=True,
                    batch=batch_size, receipt_directory=directories["processed"])
                item["load"] = result
                item["status"] = result["status"]
                if result["status"] not in ("LOADED", "SKIPPED"):
                    return reports, 2
            else:
                item["status"] = "VALIDATED"
        except Exception as exc:
            item.update(status="FAILED", error=pipeline.safe_error(exc))
            return reports, 1
        finally:
            if db is not None:
                db.close()
    return reports, 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", default="config/flightstate_jobs.json")
    parser.add_argument("--commit", action="store_true",
                        help="Write to PostgreSQL; otherwise validate only.")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args(argv)
    if not 1 <= args.batch_size <= 5000:
        parser.error("--batch-size must be between 1 and 5000")
    from src import flightstate_pipeline as pipeline
    try:
        if pipeline.VERSION != "3.2.0":
            raise ValueError("This runner requires flightstate_pipeline 3.2.0.")
        directories = pipeline.paths()
        jobs = read_jobs(pipeline, resolve_path(pipeline.ROOT, args.jobs))
        results, code = execute(pipeline, jobs, directories, args.commit, args.batch_size)
        report = {"status": "SUCCEEDED" if code == 0 else "STOPPED",
                  "mode": "COMMIT" if args.commit else "DRY_RUN", "jobs": results}
        pipeline.emit(report, directories["metadata"] / f"orchestrator-{uuid4()}.json")
        return code
    except Exception as exc:
        print(f"ORCHESTRATOR FAILED: {pipeline.safe_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
