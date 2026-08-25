variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "receiver_image" {
  description = "Image for webhook receiver service"
  type        = string
}

variable "agent_image" {
  description = "Image for the agent Cloud Run Job"
  type        = string
}

variable "agent_timeout_seconds" {
  description = "Max time an agent run is allowed"
  type        = number
  default     = 300 # 5 minutes
}


variable "agent_cpu" {
  type    = string
  default = "2"
}

variable "agent_memory" {
  type    = string
  default = "2Gi"
}

variable "max_claude_turns" {
  type    = number
  default = 30
}

# Secrets

variable "twilio_account_sid" {
  type      = string
  sensitive = true
}

variable "twilio_auth_token" {
  type      = string
  sensitive = true
}

variable "twilio_whatsapp_number" {
  description = "Twilio WhatsApp number"
  type        = string
}

variable "anthropic_api_key" {
  type      = string
  sensitive = true
}

variable "github_app_id" {
  type = string
}

variable "github_app_installation_id" {
  type = string
}

variable "github_app_private_key" {
  description = "PEM contents of GitHub App private key"
  type        = string
  sensitive   = true
}

variable "allowed_whatsapp_senders" {
  description = "List of allowed WhatsApp numbers"
  type        = list(string)
}
