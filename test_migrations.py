from pathlib import Path
import runpy


def test_alembic_revision_ids_fit_default_version_column():
    versions_dir = Path(__file__).resolve().parents[1] / "backend" / "alembic" / "versions"

    for migration_path in versions_dir.glob("*.py"):
        revision = runpy.run_path(str(migration_path)).get("revision")
        assert revision is None or len(revision) <= 32, (
            f"{migration_path.name} revision '{revision}' exceeds Alembic's default version column width"
        )
