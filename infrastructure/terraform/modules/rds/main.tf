variable "environment"           { type = string }
variable "vpc_id"                { type = string }
variable "private_subnet_ids"    { type = list(string) }
variable "kms_key_id"            { type = string }
variable "eks_security_group_id" { type = string }
variable "db_name"               { type = string }
variable "db_username"           { type = string }
variable "instance_class"        { type = string }
variable "allocated_storage"     { type = number }
variable "multi_az"              { type = bool  }

resource "aws_security_group" "rds" {
  name        = "idintel-${var.environment}-rds"
  description = "RDS PostgreSQL — allow only from EKS nodes"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.eks_security_group_id]
    description     = "PostgreSQL from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all egress"
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "idintel-${var.environment}"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "main" {
  identifier        = "idintel-${var.environment}"
  engine            = "postgres"
  engine_version    = "16.4"
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"
  storage_encrypted = true
  kms_key_id        = var.kms_key_id

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az               = var.multi_az
  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"
  deletion_protection     = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "idintel-${var.environment}-final"

  performance_insights_enabled          = true
  performance_insights_retention_period = 7
  monitoring_interval                   = 60

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  auto_minor_version_upgrade = true
  copy_tags_to_snapshot      = true
}

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "idintel/${var.environment}/db-password"
  kms_key_id              = var.kms_key_id
  recovery_window_in_days = 30
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db.result
}

output "db_endpoint"    { value = aws_db_instance.main.endpoint }
output "db_name"        { value = aws_db_instance.main.db_name }
output "db_secret_arn"  { value = aws_secretsmanager_secret.db_password.arn }
