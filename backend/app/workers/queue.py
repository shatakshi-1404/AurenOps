from app.workers.celery_app import celery


def enqueue_start(run_id: str, role: str):
    celery.send_task("run.start", args=[run_id, role])


def enqueue_resume(run_id: str, decision: dict):
    celery.send_task("run.resume", args=[run_id, decision])


def enqueue_retry(run_id: str):
    celery.send_task("run.retry", args=[run_id])


def enqueue_ingest(doc_id: str):
    celery.send_task("doc.ingest", args=[doc_id])
