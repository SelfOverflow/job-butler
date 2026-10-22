output "volume_id" {
  value = aws_ebs_volume.job_butler_data.id
}

output "volume_arn" {
  value = aws_ebs_volume.job_butler_data.arn
}
