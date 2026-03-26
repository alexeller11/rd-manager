from datetime import datetime, timezone

async def run_full_sync(client_id: int):
    return {
        "ok": True,
        "summary": {
            "counts": {
                "landing_pages": 0,
                "segmentations": 0,
                "workflows": 0,
                "campaigns": 0
            },
            "metrics": {}
        }
    }


async def get_last_summary(client_id: int):
    return {
        "client_id": client_id,
        "summary": {}
    }


async def get_last_run(client_id: int):
    return {
        "client_id": client_id,
        "status": "ok"
    }


async def list_snapshots(client_id: int, object_type=None):
    return []
