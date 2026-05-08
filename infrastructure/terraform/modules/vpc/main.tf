variable "environment"         { type = string }
variable "vpc_cidr"            { type = string }
variable "availability_zones"  { type = list(string) }
variable "public_subnet_cidrs" { type = list(string) }
variable "private_app_cidrs"   { type = list(string) }
variable "private_data_cidrs"  { type = list(string) }

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "idintel-${var.environment}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "idintel-${var.environment}-igw" }
}

resource "aws_subnet" "public" {
  count                   = length(var.public_subnet_cidrs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidrs[count.index]
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = false
  tags                    = { Name = "idintel-${var.environment}-public-${count.index + 1}" }
}

resource "aws_subnet" "private_app" {
  count             = length(var.private_app_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_app_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags              = { Name = "idintel-${var.environment}-app-${count.index + 1}" }
}

resource "aws_subnet" "private_data" {
  count             = length(var.private_data_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_data_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]
  tags              = { Name = "idintel-${var.environment}-data-${count.index + 1}" }
}

resource "aws_eip" "nat" {
  count  = length(var.public_subnet_cidrs)
  domain = "vpc"
}

resource "aws_nat_gateway" "main" {
  count         = length(var.public_subnet_cidrs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "idintel-${var.environment}-nat-${count.index + 1}" }
}

resource "aws_route_table" "private_app" {
  count  = length(var.private_app_cidrs)
  vpc_id = aws_vpc.main.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[count.index].id
  }
}

resource "aws_route_table_association" "private_app" {
  count          = length(var.private_app_cidrs)
  subnet_id      = aws_subnet.private_app[count.index].id
  route_table_id = aws_route_table.private_app[count.index].id
}

output "vpc_id"                   { value = aws_vpc.main.id }
output "private_app_subnet_ids"   { value = aws_subnet.private_app[*].id }
output "private_data_subnet_ids"  { value = aws_subnet.private_data[*].id }
output "public_subnet_ids"        { value = aws_subnet.public[*].id }
