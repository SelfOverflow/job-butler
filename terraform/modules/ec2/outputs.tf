output "instance_id" {
  value = aws_instance.job_butler.id
}

output "public_ip" {
  value = aws_instance.job_butler.public_ip
}

output "public_dns" {
  value = aws_instance.job_butler.public_dns
}
