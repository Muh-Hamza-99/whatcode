resource "google_cloud_run_v2_job" "agent_job" {
  name     = "whatsapp-agent-job"
  location = var.region

  template {
    template {
      service_account = google_service_account.agent_job.email
      timeout         = "${var.agent_job_timeout_seconds}s"
      max_retries     = 0 # let failures surface as a WhatsApp message, not a silent retry

      containers {
        image = var.agent_job_image

        # TASK_ID is overridden per-execution by the receiver when it calls
        # jobs.run() - this default is only used for manual `gcloud run jobs execute`.
        env {
          name  = "TASK_ID"
          value = ""
        }
        env {
          name  = "GCP_PROJECT"
          value = var.project_id
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
        env {
          name  = "TWILIO_WHATSAPP_NUMBER"
          value = var.twilio_whatsapp_number
        }
        env {
          name = "ANTHROPIC_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret["anthropic-api-key"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "GITHUB_APP_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret["github-app-id"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "GITHUB_APP_INSTALLATION_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret["github-app-installation-id"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "GITHUB_APP_PRIVATE_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secret["github-app-private-key"].secret_id
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = var.agent_job_cpu
            memory = var.agent_job_memory
          }
        }
      }
    }
  }

  depends_on = [google_project_service.apis]

  lifecycle {
    # The receiver overrides env vars (TASK_ID) per-execution via the API;
    # don't fight that by having Terraform "correct" it back on every apply.
    ignore_changes = [template[0].template[0].containers[0].env]
  }
}
