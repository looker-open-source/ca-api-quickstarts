terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "6.18.1"
    }
  }
}

resource "google_cloud_run_service" "cortado" {
  name     = var.app_name
  location = var.region
  project = var.project_id

  template {
    spec {
      containers {
        image = var.image
        ports {
          container_port = 8080
        }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.datastore_project_id
        }
        env {
          name  = "REDIRECT_URI"
          value = var.redirect_uri
        }
        env {
          name  = "GOOGLE_CLIENT_ID"
          value = var.google_client_id
        }
        env {
          name  = "GOOGLE_CLIENT_SECRET"
          value = var.google_client_secret
        }
        env {
          name  = "GEMINI_REGION"
          value = var.gemini_region
        }
        env {
          name  = "BQ_LOCATION"
          value = var.bq_location
        }
        env {
          name  = "MODEL"
          value = var.model
        }
        env {
          name  = "TEMPERATURE"
          value = var.temperature
        }
        env {
          name  = "TOP_P"
          value = var.top_p
        }
      }
    }
    metadata {
      annotations = {
        "autoscaling.knative.dev/maxScale" = "10" # example autoscaling max scale
      }
    }
  }

  traffic {
    latest_revision = true
    percent         = 100
  }
}
