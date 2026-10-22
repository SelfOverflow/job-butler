variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "production"
}

variable "retention_in_days" {
  type        = number
  description = "Log retention period in days"
  default     = 30
}
