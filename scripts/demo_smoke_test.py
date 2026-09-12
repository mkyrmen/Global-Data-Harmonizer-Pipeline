"""Headless demo smoke test against the configured Supabase project.

Mirrors the browser's first-run flow end to end:
  1. sign up a throwaway user (Auth)
  2. bootstrap the demo workspace (DemoService -> uploads both demo CSVs to
     Storage, inserts raw_sources + workspace_sources under that user)
  3. register a harmonization job (as the jobs router does) and run it
     through PipelineService
  4. fetch the harmonized dataset and report quality / validation

Prerequisites:
  - backend/.env populated
  - storage buckets `uploads` and `outputs` exist on the project
  - email confirmation disabled in Auth settings (otherwise sign-up yields
    no session; the browser demo would behave the same)

Usage:
    .venv/Scripts/python.exe scripts/demo_smoke_test.py

The throwaway user is NOT deleted automatically (needs a service-role/admin
key); the script prints the email for manual cleanup.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config import settings
from backend.dependencies import RequestContext, supabase_client_for
from backend.services.demo_service import DemoService
from backend.services.pipeline_service import PipelineService

EMAIL_DOMAIN = "example.com"


def main() -> int:
    if not settings.configured:
        raise SystemExit("Backend not configured: fill backend/.env and retry.")

    from supabase import create_client

    anon = create_client(settings.supabase_url, settings.supabase_anon_key)
    email = f"demo-scan-{int(time.time())}@{EMAIL_DOMAIN}"
    password = "DemoSmoke123!"

    print(f"[1/4] Sign up throwaway user {email} ...")
    auth = anon.auth.sign_up({"email": email, "password": password})
    session = auth.session
    if not session:
        raise SystemExit(
            "Sign-up returned no session. Hosted Supabase has 'Confirm email' enabled; "
            "disable it in Auth -> Providers -> Email, then retry."
        )
    user_id = auth.user.id
    ctx = RequestContext(user_id=user_id, token=session.access_token)
    print(f"      user_id={user_id}")

    print("[2/4] Bootstrap demo workspace (upload both demo CSVs + wire sources) ...")
    workspace = DemoService(ctx).ensure_demo_workspace()
    print(f"      workspace id={workspace['id']} name={workspace['name']!r}")

    client = supabase_client_for(ctx)
    links = client.table("workspace_sources").select("source_id").eq("workspace_id", workspace["id"]).execute().data
    sources = client.table("raw_sources").select("id, name, storage_path").eq("owner_id", user_id).execute().data
    source_ids = [l["source_id"] for l in links]
    names = {s["id"]: s["name"] for s in sources if s["id"] in source_ids}
    if not source_ids:
        raise SystemExit("No sources were registered for the workspace.")
    print(f"      {len(source_ids)} source(s): {[names[s] for s in source_ids]}")

    print("[3/4] Register + run harmonization job ...")
    job = (
        client.table("harmonization_jobs")
        .insert(
            {
                "owner_id": user_id,
                "workspace_id": workspace["id"],
                "name": "Smoke-test run",
                "config_json": {},
                "status": "queued",
            }
        )
        .execute()
        .data[0]
    )
    client.table("job_sources").insert(
        [{"job_id": job["id"], "source_id": sid, "sort_order": i} for i, sid in enumerate(source_ids)]
    ).execute()
    summary = PipelineService(ctx).run_job(
        job_id=job["id"],
        name=job["name"],
        workspace_id=workspace["id"],
        source_ids=source_ids,
        config_json={},
    )
    print(f"      pipeline_id={summary['pipeline_id']} status={summary['status']} "
          f"rows {summary['input_rows']}->{summary['output_rows']}")

    print("[4/4] Fetch harmonized dataset ...")
    job_row = client.table("harmonization_jobs").select("status, error_message").eq("id", job["id"]).execute().data[0]
    ds = client.table("harmonized_datasets").select("*").eq("job_id", job["id"]).eq("owner_id", user_id).execute().data
    if not ds:
        raise SystemExit("Job ran but no harmonized_dataset row was produced.")
    d = ds[0]
    print(f"      rows={d['row_count']} quality {d['quality_before']} -> {d['quality_after']} "
          f"validation={d['validation_status']}")

    ok = job_row["status"] == "succeeded" and d["validation_status"] == "PASS"
    print("\nDEMO SMOKE TEST PASSED" if ok else "\nDEMO SMOKE TEST: INCOMPLETE - see output above")
    print(f"Cleanup: delete the throwaway user {email} in Dashboard -> Authentication -> Users.")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"DEMO SMOKE TEST FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)