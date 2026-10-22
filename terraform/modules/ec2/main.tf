data "aws_ami" "ubuntu_arm" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-arm64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "job_butler" {
  name        = "job-butler-sg-${var.environment}"
  description = "Allow inbound on 8000 (UI/API) and SSH"

  ingress {
    description = "Job Butler Web Command Center"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH administration"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "job-butler-sg-${var.environment}"
    Application = "JobButler"
    Environment = var.environment
  }
}

resource "aws_iam_role" "job_butler" {
  name = "job-butler-ec2-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "job_butler_access" {
  name = "job-butler-policy-${var.environment}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = var.ssm_arn_prefix
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:log-group:/job-butler/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_access" {
  role       = aws_iam_role.job_butler.name
  policy_arn = aws_iam_policy.job_butler_access.arn
}

resource "aws_iam_instance_profile" "job_butler" {
  name = "job-butler-instance-profile-${var.environment}"
  role = aws_iam_role.job_butler.name
}

resource "aws_instance" "job_butler" {
  ami                  = data.aws_ami.ubuntu_arm.id
  instance_type        = var.instance_type
  key_name             = var.key_name
  iam_instance_profile = aws_iam_instance_profile.job_butler.name
  security_groups      = [aws_security_group.job_butler.name]

  user_data = <<-EOF
              #!/bin/bash
              set -e
              apt-get update && apt-get install -y docker.io docker-compose-v2
              systemctl enable --now docker
              mkdir -p /mnt/job_butler_data
              EOF

  tags = {
    Name        = "job-butler-${var.environment}"
    Application = "JobButler"
    Environment = var.environment
  }
}

resource "aws_volume_attachment" "ebs_att" {
  device_name = "/dev/xvdf"
  volume_id   = var.ebs_volume_id
  instance_id = aws_instance.job_butler.id
}
