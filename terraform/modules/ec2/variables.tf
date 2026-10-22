variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "production"
}

variable "instance_type" {
  type        = string
  description = "EC2 instance type (e.g. t4g.small or t3.micro)"
  default     = "t4g.small"
}

variable "key_name" {
  type        = string
  description = "Optional EC2 SSH keypair name"
  default     = null
}

variable "ebs_volume_id" {
  type        = string
  description = "Persistent EBS volume ID to attach"
}

variable "log_group_name" {
  type        = string
  description = "CloudWatch log group for container logs"
}

variable "ssm_arn_prefix" {
  type        = string
  description = "SSM ARN prefix for IAM policy"
}
