variable "environment"           { type = string }
variable "vpc_id"                { type = string }
variable "private_subnet_ids"    { type = list(string) }
variable "eks_security_group_id" { type = string }
variable "node_type"             { type = string }
variable "num_cache_clusters"    { type = number }

resource "aws_security_group" "redis" {
  name        = "idintel-${var.environment}-redis"
  description = "Redis — allow only from EKS nodes"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [var.eks_security_group_id]
    description     = "Redis from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all egress"
  }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "idintel-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "idintel-${var.environment}"
  description          = "IDIntel Ghana Redis cluster"

  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_clusters
  port                 = 6379

  subnet_group_name          = aws_elasticache_subnet_group.main.name
  security_group_ids         = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth.result
  auth_token_update_strategy = "ROTATE"

  automatic_failover_enabled = var.num_cache_clusters > 1
  multi_az_enabled           = var.num_cache_clusters > 1

  snapshot_retention_limit = 7
  snapshot_window          = "04:00-05:00"

  engine_version = "7.1"

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow.name
    destination_type = "cloudwatch-logs"
    log_format       = "json"
    log_type         = "slow-log"
  }
}

resource "aws_cloudwatch_log_group" "redis_slow" {
  name              = "/aws/elasticache/idintel-${var.environment}/slow-log"
  retention_in_days = 30
}

resource "random_password" "redis_auth" {
  length  = 32
  special = false
}

output "redis_endpoint"     { value = aws_elasticache_replication_group.main.primary_endpoint_address }
output "redis_port"         { value = 6379 }
output "redis_auth_token"   { value = random_password.redis_auth.result; sensitive = true }
