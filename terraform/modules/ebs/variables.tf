variable "availability_zone" {
  type        = string
  description = "Availability zone for the persistent EBS volume"
}

variable "volume_size" {
  type        = number
  description = "Volume size in GB"
  default     = 20
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "production"
}
