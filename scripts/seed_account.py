from app.db import SessionLocal
from app.services.discovery import DiscoveryService


if __name__ == "__main__":
    db = SessionLocal()
    svc = DiscoveryService(db)
    cfg = svc.seed_account_config(
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
    print({"account_config_id": cfg.id, "account_name": cfg.account_name})
    db.close()
