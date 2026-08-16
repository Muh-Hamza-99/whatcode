locals {
  secrets = {
    twilio-account-sid         = var.twilio_account_sid
    twilio-auth-token          = var.twilio_auth_token
    anthropic-api-key          = var.anthropic_api_key
    github-app-id              = var.github_app_id
    github-app-installation-id = var.github_app_installation_id
    github-app-private-key     = var.github_app_private_key
  }
}

resource "google_secret_manager_secret" "secret" {
  for_each  = local.secrets
  secret_id = each.key
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "secret_version" {
  for_each    = local.secrets
  secret      = google_secret_manager_secret.secret[each.key].id
  secret_data = each.value
}
