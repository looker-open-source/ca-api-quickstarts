variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "us-central1"
}

variable "app_name" {
  description = "Name of the cortado app"
  type        = string
}

variable "image" {
  description = "The image of the Cortado app"
  type        = string
}

variable "redirect_uri" {
  description = "The OAuth 2.0 redirect URI"
  type        = string
}

variable "google_client_id" {
  description = "The Google OAuth 2.0 client ID"
  type        = string
}

variable "google_client_secret" {
  description = "The Google OAuth 2.0 client secret"
  type        = string
  sensitive   = true # Mark as sensitive to prevent display in plan output
}

variable "bq_location" {
  description = "The region the data in BigQuery is located."
  type        = string
  default     = "us"
  sensitive   = false
}

variable "gemini_region" {
  description = "The region gemini will use when generating the agent."
  type        = string
  default     = "us-central1"
  sensitive   = false
}

variable "model" {
  description = "The Gemini model version the application will use to generate the agent."
  type        = string
  default     = "gemini-2.0-flash-001"
  sensitive   = false
}

variable "temperature" {
  description = "The temperature parameter the LLM to generate the agent will be set to."
  type        = number
  default     = 0.2
  sensitive   = false
}

variable "top_p" {
  description = "The top parameter the LLM to generate the agent will be set to."
  type        = number
  default     = 0.7
  sensitive   = false
}
