provider "google-beta" {
  project = var.project_id
  region  = var.region
}

resource "google_firebase_project" "default" {
  provider = google-beta
  project  = var.project_id
}

resource "google_firebase_web_app" "dashboard" {
  provider     = google-beta
  project      = var.project_id
  display_name = "whatcode-dashboard"
  depends_on   = [google_firebase_project.default]
}

# Pulls the apiKey/authDomain the dashboard's .env needs - avoids copying
# these by hand from the Firebase console.
data "google_firebase_web_app_config" "dashboard" {
  provider   = google-beta
  project    = var.project_id
  web_app_id = google_firebase_web_app.dashboard.app_id
}

# Deploys dashboard/firestore.rules so you don't need the separate
# `firebase deploy --only firestore:rules` step from the dashboard README.
resource "google_firebaserules_ruleset" "firestore" {
  provider = google-beta
  project  = var.project_id

  source {
    files {
      name    = "firestore.rules"
      content = file("${path.module}/../dashboard/firestore.rules")
    }
  }

  depends_on = [google_firebase_project.default]
}

resource "google_firebaserules_release" "firestore" {
  provider     = google-beta
  project      = var.project_id
  name         = "cloud.firestore"
  ruleset_name = "projects/${var.project_id}/rulesets/${google_firebaserules_ruleset.firestore.name}"

  lifecycle {
    replace_triggered_by = [google_firebaserules_ruleset.firestore]
  }
}

output "firebase_web_api_key" {
  value = data.google_firebase_web_app_config.dashboard.api_key
}

output "firebase_auth_domain" {
  value = data.google_firebase_web_app_config.dashboard.auth_domain
}
