resource "aws_ssm_parameter" "gemini_api_key" {
  name        = "/job-butler/${var.environment}/gemini_api_key"
  description = "Gemini API key for ATS tailoring"
  type        = "SecureString"
  value       = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "firecrawl_api_key" {
  name        = "/job-butler/${var.environment}/firecrawl_api_key"
  description = "Firecrawl API key for autonomous job discovery"
  type        = "SecureString"
  value       = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "dashboard_password_hash" {
  name        = "/job-butler/${var.environment}/dashboard_password_hash"
  description = "Scrypt password hash for web command center login"
  type        = "SecureString"
  value       = "placeholder"

  lifecycle {
    ignore_changes = [value]
  }
}
