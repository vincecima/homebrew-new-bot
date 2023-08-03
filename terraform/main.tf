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
  plaintext_value = ""

  lifecycle {
    ignore_changes = [plaintext_value]
  }
}

resource "github_actions_secret" "mastodon_client_secret" {
  repository      = "homebrew-new-bot"
  secret_name     = "mastodon_client_secret"
  plaintext_value = ""

  lifecycle {
    ignore_changes = [plaintext_value]
  }
}