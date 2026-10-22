variable "aws_region" {
  type        = string
  description = "AWS region for deployment"
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Environment identifier"
  default     = "production"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance size (t4g.small recommended for ARM64 cost efficiency)"
  default     = "t4g.small"
}

variable "key_name" {
  type        = string
  description = "Name of existing AWS EC2 KeyPair for SSH"
  default     = null
}

variable "ebs_volume_size" {
  type        = number
  description = "Persistent EBS volume size in GB"
  default     = 20
}
