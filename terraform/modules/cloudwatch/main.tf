resource "aws_cloudwatch_log_group" "job_butler" {
  name              = "/job-butler/${var.environment}"
  retention_in_days = var.retention_in_days

  tags = {
    Application = "JobButler"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_metric_filter" "app_errors" {
  name           = "JobButlerErrors-${var.environment}"
  pattern        = "[timestamp, level = ERROR*, ...]"
  log_group_name = aws_cloudwatch_log_group.job_butler.name

  metric_transformation {
    name      = "ErrorCount"
    namespace = "JobButler/${var.environment}"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "high_errors" {
  alarm_name          = "job-butler-${var.environment}-high-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ErrorCount"
  namespace           = "JobButler/${var.environment}"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Triggers when Job Butler encounters elevated runtime errors"
}
