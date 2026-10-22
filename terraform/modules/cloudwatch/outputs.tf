output "log_group_name" {
  value = aws_cloudwatch_log_group.job_butler.name
}

output "log_group_arn" {
  value = aws_cloudwatch_log_group.job_butler.arn
}

output "alarm_arn" {
  value = aws_cloudwatch_metric_alarm.high_errors.arn
}
