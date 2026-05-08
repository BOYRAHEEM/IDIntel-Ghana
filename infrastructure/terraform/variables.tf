variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "af-south-1"
}

variable "environment" {
  description = "Deployment environment: development, staging, or production"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be one of: development, staging, production"
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["af-south-1a", "af-south-1b", "af-south-1c"]
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.0.0.0/20", "10.0.16.0/20", "10.0.32.0/20"]
}

variable "private_app_subnet_cidrs" {
  type    = list(string)
  default = ["10.0.48.0/20", "10.0.64.0/20", "10.0.80.0/20"]
}

variable "private_data_subnet_cidrs" {
  type    = list(string)
  default = ["10.0.96.0/20", "10.0.112.0/20", "10.0.128.0/20"]
}

variable "eks_cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.31"
}

variable "eks_node_groups" {
  description = "EKS managed node group configurations"
  type = map(object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
    desired_size   = number
    disk_size_gb   = number
  }))
  default = {
    api_services = {
      instance_types = ["m6i.xlarge"]
      min_size       = 2
      max_size       = 10
      desired_size   = 3
      disk_size_gb   = 50
    }
    ml_inference = {
      instance_types = ["c6i.2xlarge"]
      min_size       = 1
      max_size       = 5
      desired_size   = 2
      disk_size_gb   = 100
    }
  }
}

variable "db_name" {
  type    = string
  default = "idintel_production"
}

variable "db_username" {
  type    = string
  default = "idintel_app"
}

variable "rds_instance_class" {
  type    = string
  default = "db.r6g.xlarge"
}

variable "rds_allocated_storage" {
  type    = number
  default = 500
}

variable "redis_node_type" {
  type    = string
  default = "cache.r7g.large"
}
