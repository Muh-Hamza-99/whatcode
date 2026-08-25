"""
Cloud Run Job entrypoint. Runs once per WhatsApp-triggered task:

  1. load task from Firestore (prompt, requester)
  2. figure out / create the target GitHub repo
  3. run `claude -p` (headless Claude Code) against a fresh clone
  4. commit, push, open a PR
  5. report progress and the final result back over WhatsApp
  6. record the outcome in Firestore

Every external call is wrapped so a failure still produces a WhatsApp
message and a Firestore status update instead of just dying silently in
Cloud Logging.
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from google.cloud import firestore
from twilio.rest import Client as TwilioClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent")

PROJECT = os.environ["GCP_PROJECT"]
TASK_ID = os.environ["TASK_ID"]

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_NUMBER = os.environ["TWILIO_WHATSAPP_NUMBER"]  # "whatsapp:+1..."

GITHUB_APP_ID = os.environ["GITHUB_APP_ID"]
GITHUB_APP_INSTALLATION_ID = os.environ["GITHUB_APP_INSTALLATION_ID"]
GITHUB_APP_PRIVATE_KEY = os.environ["GITHUB_APP_PRIVATE_KEY"]

# Default org/user to create repos under when the prompt doesn't specify one.
DEFAULT_GITHUB_OWNER = os.environ.get("DEFAULT_GITHUB_OWNER", "")

MAX_CLAUDE_TURNS = int(os.environ.get("MAX_CLAUDE_TURNS", "30"))

db = firestore.Client(project=PROJECT)
twilio = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def main() -> None:
    if not TASK_ID:
        log.error("TASK_ID not set - was this run manually without an override?")
        sys.exit(1)

    task_ref = db.collection("tasks").document(TASK_ID)
    task = task_ref.get()
    if not task.exists:
        log.error("no such task %s", TASK_ID)
        sys.exit(1)

    data = task.to_dict()
    prompt = data["prompt"]
    requester = data["from_whatsapp"]

    try:
        _update(task_ref, status="running", started_at=firestore.SERVER_TIMESTAMP)
        _notify(requester, f"🚀 Starting: {prompt[:200]}")

        github_token = _github_installation_token()
        repo_name, repo_url = _resolve_repo(prompt, github_token)
        _update(task_ref, repo=repo_url)
        _notify(requester, f"📦 Using repo {repo_url}")

        with tempfile.TemporaryDirectory() as workdir:
            repo_dir = _clone(repo_url, github_token, workdir)
            branch = f"agent/{TASK_ID[:8]}"
            _run(["git", "checkout", "-b", branch], cwd=repo_dir)

            _notify(requester, "🤖 Claude Code is working on it...")
            _run_claude_code(prompt, repo_dir)

            if not _has_changes(repo_dir):
                _update(task_ref, status="no_changes")
                _notify(requester, "🤔 Finished, but no changes were made. Nothing to commit.")
                return

            _run(["git", "add", "-A"], cwd=repo_dir)
            _run(
                ["git", "-c", "user.name=agent-bot", "-c", "user.email=agent-bot@users.noreply.github.com",
                 "commit", "-m", f"Automated change: {prompt[:72]}"],
                cwd=repo_dir,
            )
            _run(["git", "push", "-u", "origin", branch], cwd=repo_dir)

            pr_url = _open_pr(repo_dir, branch, prompt, github_token)
            _update(task_ref, status="done", pr_url=pr_url, finished_at=firestore.SERVER_TIMESTAMP)
            _notify(requester, f"✅ Done! Pull request: {pr_url}")

    except Exception as exc:  # noqa: BLE001
        log.exception("task %s failed", TASK_ID)
        _update(task_ref, status="failed", error=str(exc), finished_at=firestore.SERVER_TIMESTAMP)
        _notify(requester, f"❌ Task failed: {exc}")
        sys.exit(1)


# --- helpers -----------------------------------------------------------

def _update(ref, **fields) -> None:
    ref.update(fields)


def _notify(to_whatsapp: str, body: str) -> None:
    try:
        twilio.messages.create(from_=TWILIO_WHATSAPP_NUMBER, to=to_whatsapp, body=body)
    except Exception:  # noqa: BLE001
        log.exception("failed to send WhatsApp notification (continuing)")


def _run(cmd, cwd=None, check=True, capture=False):
    log.info("$ %s", " ".join(cmd))
    return subprocess.run(
        cmd, cwd=cwd, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        text=True,
    )


def _github_installation_token() -> str:
    """Mint a short-lived GitHub App installation token via `gh`'s
    built-in app-token support (gh auth uses GITHUB_TOKEN if set; here we
    exchange the App private key ourselves with a small JWT + REST call)."""
    import jwt  # PyJWT

    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": GITHUB_APP_ID}
    app_jwt = jwt.encode(payload, GITHUB_APP_PRIVATE_KEY, algorithm="RS256")

    result = _run(
        [
            "curl", "-s", "-X", "POST",
            "-H", f"Authorization: Bearer {app_jwt}",
            "-H", "Accept: application/vnd.github+json",
            f"https://api.github.com/app/installations/{GITHUB_APP_INSTALLATION_ID}/access_tokens",
        ],
        capture=True,
    )
    token = json.loads(result.stdout)["token"]
    return token


def _resolve_repo(prompt: str, github_token: str) -> tuple[str, str]:
    """Very simple v1 heuristic: look for `repo:owner/name` in the prompt.
    Falls back to creating a new repo under DEFAULT_GITHUB_OWNER named after
    a slugified version of the prompt. Swap this out for real intent
    parsing (or a Claude call) once the basic pipeline works end to end."""
    match = re.search(r"repo:([\w.-]+/[\w.-]+)", prompt)
    if match:
        full_name = match.group(1)
        os.environ["GH_TOKEN"] = github_token
        _run(["gh", "repo", "view", full_name])  # raises if it doesn't exist / no access
        return full_name, f"https://github.com/{full_name}.git"

    slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40] or "agent-task"
    owner = DEFAULT_GITHUB_OWNER
    full_name = f"{owner}/{slug}-{TASK_ID[:6]}"
    os.environ["GH_TOKEN"] = github_token
    _run(["gh", "repo", "create", full_name, "--private", "--add-readme"])
    return full_name, f"https://github.com/{full_name}.git"


def _clone(repo_url: str, github_token: str, workdir: str) -> str:
    auth_url = repo_url.replace("https://", f"https://x-access-token:{github_token}@")
    repo_dir = str(Path(workdir) / "repo")
    _run(["git", "clone", auth_url, repo_dir])
    return repo_dir


def _run_claude_code(prompt: str, repo_dir: str) -> None:
    _run(
        [
            "claude", "-p", prompt,
            "--allowedTools", "Read,Edit,Write,Bash,Glob,Grep",
            "--dangerously-skip-permissions",
            "--max-turns", str(MAX_CLAUDE_TURNS),
        ],
        cwd=repo_dir,
    )


def _has_changes(repo_dir: str) -> bool:
    result = _run(["git", "status", "--porcelain"], cwd=repo_dir, capture=True)
    return bool(result.stdout.strip())


def _open_pr(repo_dir: str, branch: str, prompt: str, github_token: str) -> str:
    os.environ["GH_TOKEN"] = github_token
    result = _run(
        [
            "gh", "pr", "create",
            "--title", f"Automated: {prompt[:72]}",
            "--body", f"Opened automatically from a WhatsApp request.\n\nPrompt:\n\n{prompt}",
            "--head", branch,
        ],
        cwd=repo_dir,
        capture=True,
    )
    return result.stdout.strip().splitlines()[-1]


if __name__ == "__main__":
    main()
