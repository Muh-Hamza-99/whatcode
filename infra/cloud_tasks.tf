resource "google_cloud_tasks_queue" "agent_tasks" {
  name     = "agent-tasks"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 5
    max_dispatches_per_second = 2
  }

  retry_config {
    max_attempts  = 3
    min_backoff   = "10s"
    max_backoff   = "60s"
    max_doublings = 2
  }

  depends_on = [google_project_service.apis]
}
