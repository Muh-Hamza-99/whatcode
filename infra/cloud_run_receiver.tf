resource "google_cloud_run_v2_service" "receiver" {
  name     = "whatsapp-agent-receiver"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # must stay public - Twilio calls this directly

  template {
    service_account = google_service_account.receiver.email

    containers {
      image = var.receiver_image

      env {
        name  = "GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "TASKS_QUEUE"
        value = google_cloud_tasks_queue.agent_tasks.name
      }
      env {
        name  = "AGENT_JOB_NAME"
        value = google_cloud_run_v2_job.agent_job.name
      }
      env {
        name  = "TASKS_INVOKER_SA"
        value = google_service_account.tasks_invoker.email
      }
      env {
        name  = "ALLOWED_SENDERS"
        value = join(",", var.allowed_whatsapp_senders)
      }
      env {
        name = "TWILIO_ACCOUNT_SID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret["twilio-account-sid"].secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "TWILIO_AUTH_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.secret["twilio-auth-token"].secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# Public unauthenticated ingress on the *service* is required for the Twilio
# webhook path; the /internal/run-job path is protected in application code
# by verifying the Cloud-Tasks-issued OIDC token instead of relying on
# Cloud Run's per-service IAM (which can't be split per-route).
resource "google_cloud_run_v2_service_iam_member" "receiver_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.receiver.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
