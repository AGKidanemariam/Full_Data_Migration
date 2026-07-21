from datetime import datetime

from src.common.manifest import record_manifest


record_manifest(
    run_id="TEST001",
    stage="Extract",
    file_name="customers.zip",
    sha256="ABC123",
    status="Success",
    started_at=datetime.now(),
    finished_at=datetime.now(),
    records_read=100,
    records_written=100,
    records_rejected=0,
    message="Test successful.",
)

print("Manifest record written successfully.")
