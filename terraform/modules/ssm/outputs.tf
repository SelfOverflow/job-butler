output "arn_prefix" {
  value = "arn:aws:ssm:*:*:parameter/job-butler/${var.environment}/*"
}
