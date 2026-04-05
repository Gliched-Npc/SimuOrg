# backend/workers/celery_app.py


from celery import Celery
import os

BROKER_URL  = os.getenv("CELERY_BROKER_URL",  "amqp://guest:guest@localhost:5672//")
BACKEND_URL = os.getenv("CELERY_BACKEND_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "simuorg",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=["backend.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker — sims are heavy
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=10,
    broker_transport_options={"visibility_timeout": 86400},  # allows tasks to take up to 24 hours safely
    broker_heartbeat=0,  # prevents RabbitMQ dropping connection during long-running tasks
)