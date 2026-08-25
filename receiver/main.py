"""
Webhook receiver for the WhatsApp -> coding agent pipeline.

Two routes, one service:
  POST /webhook/whatsapp   - public. Twilio calls this when a WhatsApp
                              message arrives. Validated via Twilio's
                              request signature.
  POST /internal/run-job   - "private". Cloud Tasks calls this to actually
                              kick off the Cloud Run Job. Validated by
                              checking the Google-issued OIDC token Cloud
                              Tasks attaches to the request, since Cloud Run
                              ingress auth can't be split per-route on a
                              single service.
"""
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request, HTTPException
from google.auth.transport import requests as google_requests
from google.cloud import firestore
from google.cloud import run_v2
from google.cloud import tasks_v2
from google.oauth2 import id_token
from twilio.request_validator import RequestValidator

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("receiver")

app = FastAPI()

PROJECT = os.environ["GCP_PROJECT"]
REGION = os.environ["GCP_REGION"]
QUEUE = os.environ["TASKS_QUEUE"]
AGENT_NAME = os.environ["AGENT_NAME"]
TASKS_INVOKER_SA = os.environ["TASKS_INVOKER_SA"]
ALLOWED_SENDERS = {s.strip() for s in os.environ.get("ALLOWED_SENDERS", "").split(",") if s.strip()}
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]

db = firestore.Client(project=PROJECT)
tasks_client = tasks_v2.CloudTasksClient()
validator = RequestValidator(TWILIO_AUTH_TOKEN)

SERVICE_URL = os.environ.get("K_SERVICE_URL")  # set below at startup if unset


def _self_url(request: Request) -> str:
    """Best-effort absolute base URL of this running service, used to build
    the Cloud Tasks callback target."""
    return f"https://{request.headers.get('host')}"


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url).replace("http://", "https://", 1)  # Twilio always uses https in signature validation

    if not validator.validate(url, dict(form), signature):
        raise HTTPException(status_code=403, detail="invalid Twilio signature")

    from_number = form.get("From", "")  # e.g. "whatsapp:+15551234567"
    body = (form.get("Body") or "").strip()
    message_sid = form.get("MessageSid", "")

    sender = from_number.replace("whatsapp:", "")
    if ALLOWED_SENDERS and sender not in ALLOWED_SENDERS:
        log.warning("rejected message from non-allow-listed sender %s", sender)
        return {"status": "ignored"}

    if not body:
        return {"status": "ignored"}

    # Dedupe on Twilio's message id in case of webhook retries.
    task_ref = db.collection("tasks").document(message_sid or str(uuid.uuid4()))
    existing = task_ref.get()
    if existing.exists:
        log.info("duplicate delivery for %s, ignoring", message_sid)
        return {"status": "duplicate"}

    task_ref.set(
        {
            "status": "queued",
            "from_whatsapp": from_number,
            "prompt": body,
            "created_at": firestore.SERVER_TIMESTAMP,
            "repo": None,
            "pr_url": None,
            "error": None,
        }
    )

    _enqueue_run_job(task_id=task_ref.id, base_url=_self_url(request))
    return {"status": "queued", "task_id": task_ref.id}


def _enqueue_run_job(task_id: str, base_url: str) -> None:
    parent = tasks_client.queue_path(PROJECT, REGION, QUEUE)
    target_url = f"{base_url}/internal/run-job"

    task = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": target_url,
            "headers": {"Content-Type": "application/json"},
            "body": f'{{"task_id": "{task_id}"}}'.encode(),
            "oidc_token": {
                "service_account_email": TASKS_INVOKER_SA,
                "audience": target_url,
            },
        }
    }
    tasks_client.create_task(parent=parent, task=task)
    log.info("enqueued task %s", task_id)


@app.post("/internal/run-job")
async def run_job(request: Request):
    _verify_oidc(request)

    payload = await request.json()
    task_id = payload["task_id"]

    job_client = run_v2.JobsClient()
    job_path = job_client.job_path(PROJECT, REGION, AGENT_NAME)

    request_obj = run_v2.RunJobRequest(
        name=job_path,
        overrides=run_v2.RunJobRequest.Overrides(
            container_overrides=[
                run_v2.RunJobRequest.Overrides.ContainerOverride(
                    env=[run_v2.EnvVar(name="TASK_ID", value=task_id)]
                )
            ]
        ),
    )
    job_client.run_job(request=request_obj)
    log.info("started agent job execution for task %s", task_id)
    return {"status": "started", "task_id": task_id}


def _verify_oidc(request: Request) -> None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.removeprefix("Bearer ")

    try:
        claims = id_token.verify_oauth2_token(token, google_requests.Request())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc

    if claims.get("email") != TASKS_INVOKER_SA:
        raise HTTPException(status_code=403, detail="unexpected caller")


@app.get("/healthz")
async def healthz():
    return {"ok": True, "ts": time.time()}
