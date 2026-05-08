terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.33"
    }
  }
  backend "s3" {
    bucket         = "idintel-ghana-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "af-south-1"
    encrypt        = true
    dynamodb_table = "idintel-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "IDIntel-Ghana"
      Environment = var.environment
      ManagedBy   = "Terraform"
      SecurityClass = "RESTRICTED"
    }
  }
}

# ============================================================
# VPC
# ============================================================
module "vpc" {
  source = "./modules/vpc"

  environment         = var.environment
  vpc_cidr            = var.vpc_cidr
  availability_zones  = var.availability_zones
  public_subnet_cidrs = var.public_subnet_cidrs
  private_app_cidrs   = var.private_app_subnet_cidrs
  private_data_cidrs  = var.private_data_subnet_cidrs
}

# ============================================================
# KMS Keys
# ============================================================
module "kms" {
  source = "./modules/kms"

  environment = var.environment
}

# ============================================================
# EKS Cluster
# ============================================================
module "eks" {
  source = "./modules/eks"

  environment      = var.environment
  cluster_version  = var.eks_cluster_version
  vpc_id           = module.vpc.vpc_id
  private_subnets  = module.vpc.private_app_subnet_ids
  node_groups      = var.eks_node_groups
}

# ============================================================
# RDS PostgreSQL (Encrypted, Multi-AZ)
# ============================================================
module "rds" {
  source = "./modules/rds"

  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_data_subnet_ids
  kms_key_id            = module.kms.identity_key_id
  eks_security_group_id = module.eks.node_security_group_id
  db_name               = var.db_name
  db_username           = var.db_username
  instance_class        = var.rds_instance_class
  allocated_storage     = var.rds_allocated_storage
  multi_az              = var.environment == "production"
}

# ============================================================
# ElastiCache Redis (TLS, Cluster Mode)
# ============================================================
module "elasticache" {
  source = "./modules/elasticache"

  environment           = var.environment
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_data_subnet_ids
  eks_security_group_id = module.eks.node_security_group_id
  node_type             = var.redis_node_type
  num_cache_clusters    = var.environment == "production" ? 3 : 1
}

# ============================================================
# S3 Buckets
# ============================================================
resource "aws_s3_bucket" "reports" {
  bucket        = "idintel-ghana-reports-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment != "production"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms.reports_key_id
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket" "audit" {
  bucket        = "idintel-ghana-audit-${var.environment}-${data.aws_caller_identity.current.account_id}"
  force_destroy = false  # Never auto-delete audit logs
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = module.kms.audit_key_id
    }
    bucket_key_enabled = true
  }
}

# WORM policy for audit bucket — 7-year retention
resource "aws_s3_bucket_object_lock_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    default_retention {
      mode  = "COMPLIANCE"
      years = 7
    }
  }
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================================
# WAF (Web Application Firewall)
# ============================================================
resource "aws_wafv2_web_acl" "api_gateway" {
  name  = "idintel-api-waf-${var.environment}"
  scope = "REGIONAL"

  default_action { allow {} }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSet"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 2
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLiRuleSet"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "IPRateLimit"
    priority = 3
    action { count {} }
    statement {
      rate_based_statement {
        limit              = 10000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "IPRateLimit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "IDIntelAPI"
    sampled_requests_enabled   = true
  }
}

data "aws_caller_identity" "current" {}
