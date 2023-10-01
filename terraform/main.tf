terraform {
  required_providers {
    github = {
      source  = "integrations/github"
      version = "5.32.0"
    }
  }

  required_version = ">= 1.5.4"
}

variable "github_token" {
  description = "Personal access token for GitHub"
  type        = string
  sensitive   = true
}

provider "github" {
  token = var.github_token
}

resource "github_actions_variable" "log_level" {
  repository    = "homebrew-new-bot"
  variable_name = "LOG_LEVEL"
  value         = "INFO"
}

resource "github_actions_variable" "max_toots_per_execution" {
  repository    = "homebrew-new-bot"
  variable_name = "MAX_TOOTS_PER_EXECUTION"
  value         = "3"
}

resource "github_actions_variable" "mastodon_api_base_url" {
  repository    = "homebrew-new-bot"
  variable_name = "MASTODON_API_BASE_URL"
  value         = "https://botsin.space"
}

resource "github_actions_secret" "mastodon_access_token" {
  repository      = "homebrew-new-bot"
  secret_name     = "mastodon_access_token"
  encrypted_value = "k8Z0ULkcjcQyfe1QyrQLsu+zgxwLWTxaf3/Xj6yVZlhvOCbiEIwby/6PZnvGVYvrHzzqgI0qkksEdNFjeV3K5PFz6m6k8S+Cp+ZgkvzAkPrRyoGSSFMGT8i6fg=="
}

resource "github_actions_secret" "mastodon_client_secret" {
  repository      = "homebrew-new-bot"
  secret_name     = "mastodon_client_secret"
  encrypted_value = "9TYAljpmhL8JkO6yFAy9aHpmQwd9uw8citN4zjDzQ26mbwAqiIx7PZ8EOe4i64c55ADjkDmwfvSc/C4hm+UCCUqvTptD063hQZaPD933v/92aVZ2d0G8+FuUDg=="
}