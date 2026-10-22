terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {
  state = "available"
}

module "ssm" {
  source      = "./modules/ssm"
  environment = var.environment
}

module "cloudwatch" {
  source      = "./modules/cloudwatch"
  environment = var.environment
}

module "ebs" {
  source            = "./modules/ebs"
  environment       = var.environment
  availability_zone = data.aws_availability_zones.available.names[0]
  volume_size       = var.ebs_volume_size
}

module "ec2" {
  source         = "./modules/ec2"
  environment    = var.environment
  instance_type  = var.instance_type
  key_name       = var.key_name
  ebs_volume_id  = module.ebs.volume_id
  log_group_name = module.cloudwatch.log_group_name
  ssm_arn_prefix = module.ssm.arn_prefix
}
