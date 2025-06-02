# Web Server Module

variable "environment" {
  description = "The environment (dev, staging, prod)"
  type        = string
}

variable "instance_count" {
  description = "Number of instances to create"
  type        = number
  default     = 1
}

variable "instance_type" {
  description = "The instance type to use"
  type        = string
  default     = "t3.micro"
}

variable "region" {
  description = "The AWS region to deploy to"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "The VPC ID to deploy into"
  type        = string
}

variable "subnet_ids" {
  description = "The subnet IDs to deploy into"
  type        = list(string)
}

variable "tags" {
  description = "Additional tags for resources"
  type        = map(string)
  default     = {}
}

# Security Group for Web Servers
resource "aws_security_group" "web" {
  name        = "web-${var.environment}"
  description = "Security group for web servers in ${var.environment}"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS"
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
    description = "SSH from internal network"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(
    {
      Name        = "web-sg-${var.environment}"
      Environment = var.environment
      Managed_by  = "terraform"
    },
    var.tags
  )
}

# Web Server Instances
resource "aws_instance" "web" {
  count         = var.instance_count
  ami           = data.aws_ami.amazon_linux.id
  instance_type = var.instance_type
  subnet_id     = element(var.subnet_ids, count.index % length(var.subnet_ids))

  vpc_security_group_ids = [aws_security_group.web.id]

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 20
    delete_on_termination = true
    encrypted             = true
  }

  tags = merge(
    {
      Name        = "web-${var.environment}-${count.index + 1}"
      Environment = var.environment
      Role        = "web"
      Managed_by  = "terraform"
    },
    var.tags
  )

  volume_tags = merge(
    {
      Name        = "web-${var.environment}-${count.index + 1}"
      Environment = var.environment
      Managed_by  = "terraform"
    },
    var.tags
  )
}

# Latest Amazon Linux AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Load Balancer
resource "aws_lb" "web" {
  name               = "web-lb-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.web.id]
  subnets            = var.subnet_ids

  enable_deletion_protection = var.environment == "prod" ? true : false

  tags = merge(
    {
      Name        = "web-lb-${var.environment}"
      Environment = var.environment
      Managed_by  = "terraform"
    },
    var.tags
  )
}

# Target Group
resource "aws_lb_target_group" "web" {
  name     = "web-tg-${var.environment}"
  port     = 80
  protocol = "HTTP"
  vpc_id   = var.vpc_id

  health_check {
    path                = "/health"
    port                = "traffic-port"
    healthy_threshold   = 3
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
  }

  tags = merge(
    {
      Name        = "web-tg-${var.environment}"
      Environment = var.environment
      Managed_by  = "terraform"
    },
    var.tags
  )
}

# Target Group Attachment
resource "aws_lb_target_group_attachment" "web" {
  count            = var.instance_count
  target_group_arn = aws_lb_target_group.web.arn
  target_id        = aws_instance.web[count.index].id
  port             = 80
}

# Listener
resource "aws_lb_listener" "web_http" {
  load_balancer_arn = aws_lb.web.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}

# Outputs
output "instance_ids" {
  description = "IDs of the created instances"
  value       = aws_instance.web[*].id
}

output "instance_private_ips" {
  description = "Private IPs of the created instances"
  value       = aws_instance.web[*].private_ip
}

output "instance_public_ips" {
  description = "Public IPs of the created instances"
  value       = aws_instance.web[*].public_ip
}

output "security_group_id" {
  description = "ID of the security group"
  value       = aws_security_group.web.id
}

output "load_balancer_dns" {
  description = "DNS name of the load balancer"
  value       = aws_lb.web.dns_name
}