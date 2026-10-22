output "public_ip" {
  description = "Public IP address of Job Butler EC2 instance"
  value       = module.ec2.public_ip
}

output "ui_url" {
  description = "Job Butler Web Command Center URL"
  value       = "http://${module.ec2.public_ip}:8000"
}

output "ebs_volume_id" {
  description = "Persistent EBS Volume ID"
  value       = module.ebs.volume_id
}

output "log_group_name" {
  description = "CloudWatch log group for Job Butler runtime"
  value       = module.cloudwatch.log_group_name
}
