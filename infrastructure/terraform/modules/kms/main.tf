variable "environment" { type = string }

resource "aws_kms_key" "identity" {
  description             = "IDIntel Ghana — identity field encryption (${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = false

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })
}

resource "aws_kms_alias" "identity" {
  name          = "alias/idintel-${var.environment}-identity"
  target_key_id = aws_kms_key.identity.key_id
}

resource "aws_kms_key" "audit" {
  description             = "IDIntel Ghana — audit log signing (${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "audit" {
  name          = "alias/idintel-${var.environment}-audit"
  target_key_id = aws_kms_key.audit.key_id
}

resource "aws_kms_key" "reports" {
  description             = "IDIntel Ghana — report storage (${var.environment})"
  deletion_window_in_days = 30
  enable_key_rotation     = true
}

resource "aws_kms_alias" "reports" {
  name          = "alias/idintel-${var.environment}-reports"
  target_key_id = aws_kms_key.reports.key_id
}

data "aws_caller_identity" "current" {}

output "identity_key_id"  { value = aws_kms_key.identity.arn }
output "audit_key_id"     { value = aws_kms_key.audit.arn }
output "reports_key_id"   { value = aws_kms_key.reports.arn }
