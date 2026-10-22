resource "aws_ebs_volume" "job_butler_data" {
  availability_zone = var.availability_zone
  size              = var.volume_size
  type              = "gp3"
  encrypted         = true

  tags = {
    Name        = "job-butler-data-${var.environment}"
    Application = "JobButler"
    Environment = var.environment
  }
}
