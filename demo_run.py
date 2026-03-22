from app.db import SessionLocal
from app.services.pipeline import PipelineService


if __name__ == "__main__":
    db = SessionLocal()
    svc = PipelineService(db)
    run = svc.run_for_account(
        account_name="DuPont Tedlar",
        target_segment="Graphics & Signage",
        icp_themes=[
            "protective films",
            "signage",
            "graphics",
            "vehicle wraps",
            "architectural graphics",
            "wallcoverings",
            "durable surfaces",
            "anti-graffiti",
            "UV/weather resistance",
        ],
    )
    print({"job_run_id": run.id, "status": run.status, "details": run.details})
    db.close()
