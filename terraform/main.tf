terraform {
  required_providers {
    github = {
      source = "integrations/github"
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
  repository       = "homebrew-new-bot"
  variable_name    = "LOG_LEVEL"
  value            = "INFO"
}

resource "github_actions_variable" "max_toots_per_execution" {
  repository       = "homebrew-new-bot"
  variable_name    = "MAX_TOOTS_PER_EXECUTION"
  value            = "3"
}

resource "github_actions_secret" "toot_config" {
  repository       = "homebrew-new-bot"
  secret_name      = "TOOT_CONFIG"
  plaintext_value  = ""

  lifecycle {
    ignore_changes = [plaintext_value]
  }
}