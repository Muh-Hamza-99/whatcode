output "receiver_url" {
  description = "Point Twilio's WhatsApp webhook at {this}/webhook/whatsapp"
  value       = google_cloud_run_v2_service.receiver.uri
}

output "agent_job_name" {
  value = google_cloud_run_v2_job.agent_job.name
}

output "tasks_queue_id" {
  value = google_cloud_tasks_queue.agent_tasks.id
}

output "artifact_registry_repo" {
  value = google_artifact_registry_repository.images.name
}
