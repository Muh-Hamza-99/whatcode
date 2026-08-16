# Receiver Cloud Run service
resource "google_service_account" "receiver" {
  account_id   = "whatcode-receiver"
  display_name = "Whatcode - webhook receiver"
}

# Agent Cloud Run Job
resource "google_service_account" "agent_job" {
  account_id   = "whatcode-job"
  display_name = "Whatcode - coding job"
}

# Used by Cloud Tasks to call back receiver's internal endpoint (OIDC)
resource "google_service_account" "tasks_invoker" {
  account_id   = "whatcode-tasks"
  display_name = "Whatcode - Cloud Tasks invoker"
}

# Used by receiver needs to read secrets and write/read Firestore task docs.
resource "google_secret_manager_secret_iam_member" "receiver_secrets" {
  for_each  = toset(["twilio-account-sid", "twilio-auth-token"])
  secret_id = google_secret_manager_secret.secret[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.receiver.email}"
}

resource "google_project_iam_member" "receiver_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.receiver.email}"
}

# Used by receiver to enqueue Cloud Tasks and execute the agent job
resource "google_project_iam_member" "receiver_tasks_enqueuer" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.receiver.email}"
}

resource "google_project_iam_member" "receiver_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.receiver.email}"
}

# Used by receiver needs to generate/verify OIDC tokens for Cloud Tasks
resource "google_service_account_iam_member" "receiver_can_act_as_tasks_invoker" {
  service_account_id = google_service_account.tasks_invoker.name
  role                = "roles/iam.serviceAccountTokenCreator"
  member              = "serviceAccount:${google_service_account.receiver.email}"
}

# Cloud Tasks (using tasks_invoker SA) is allowed to call the receiver's
# /internal/run-job endpoint.
resource "google_cloud_run_v2_service_iam_member" "tasks_can_invoke_receiver" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.receiver.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tasks_invoker.email}"
}

# Agent job needs its own secrets and Firestore access
resource "google_secret_manager_secret_iam_member" "agent_job_secrets" {
  for_each  = local.secrets
  secret_id = google_secret_manager_secret.secret[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_job.email}"
}

resource "google_project_iam_member" "agent_job_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent_job.email}"
}
