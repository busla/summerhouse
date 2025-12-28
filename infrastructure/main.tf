# Summerhouse: Agent-First Vacation Rental Booking Platform
# Main Terraform configuration
#
# ⚠️ IMPORTANT: All terraform commands MUST be run via Taskfile.yaml
# Syntax: task tf:<action>:<env>
# Examples: task tf:init:dev, task tf:plan:prod, task tf:apply:dev

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.27"
    }
  }

  # Backend configuration loaded from environments/{env}-backend.config
  backend "s3" {}
}

provider "aws" {}

# Local values for resource naming
locals {
  name_prefix = "summerhouse-${var.environment}"
}

# DynamoDB Tables
module "dynamodb" {
  source = "./modules/dynamodb"

  name_prefix = local.name_prefix
  environment = var.environment
}

# AgentCore Runtime (PREREQUISITE: terraform-aws-agentcore module must exist)
# Uncomment when module is available:
# module "agentcore" {
#   source = var.agentcore_module_path
#
#   name_prefix = local.name_prefix
#   environment = var.environment
#
#   # Agent configuration
#   bedrock_model_id = var.bedrock_model_id
#
#   # DynamoDB table references
#   dynamodb_table_arns = module.dynamodb.table_arns
# }

# Cognito Passwordless (PREREQUISITE: cognito-passwordless module must exist)
# Uncomment when module is available:
# module "cognito" {
#   source = "${var.agentcore_module_path}/modules/cognito-passwordless"
#
#   name_prefix   = local.name_prefix
#   environment   = var.environment
#
#   # SES Configuration
#   ses_from_email = var.ses_from_email
#
#   # Verification settings
#   code_ttl_seconds = 300  # 5 minutes
#   max_attempts     = 3
# }

# Static Website (PREREQUISITE: static-website module must exist)
# Uncomment when module is available:
# module "static_website" {
#   source = "${var.agentcore_module_path}/modules/static-website"
#
#   name_prefix        = local.name_prefix
#   environment        = var.environment
#   domain_name        = var.domain_name
#   certificate_arn    = var.certificate_arn
#   frontend_build_dir = "${path.root}/../frontend/out"
# }
