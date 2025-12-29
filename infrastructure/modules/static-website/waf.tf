# Static Website Module - WAF Resources
# AWS WAF protection for CloudFront distribution
#
# Architecture:
# - WAF Web ACL with deny-by-default (block all non-whitelisted IPs)
# - IP Set for allowlisted IP addresses
# - Optional AWS Managed Rule Groups
#
# Note: All WAF resources must be in us-east-1 for CloudFront scope
# Uses provider alias: aws.us_east_1

# -----------------------------------------------------------------------------
# CloudPosse Label for WAF resources
# -----------------------------------------------------------------------------

module "waf_label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  # Inherit from main label, add WAF-specific naming
  context    = module.label.context
  attributes = ["waf"]
}

# -----------------------------------------------------------------------------
# WAF IP Set for Allowlisted IPs
# -----------------------------------------------------------------------------

resource "aws_wafv2_ip_set" "allowlist" {
  count = var.enable_waf ? 1 : 0

  provider           = aws.us_east_1
  name               = "${module.waf_label.id}-allowlist"
  scope              = "CLOUDFRONT"
  ip_address_version = "IPV4"
  addresses          = [for entry in var.waf_whitelisted_ips : entry.ip]

  tags = module.waf_label.tags
}

# -----------------------------------------------------------------------------
# WAF Web ACL (using cloudposse/waf/aws)
# -----------------------------------------------------------------------------

module "waf" {
  count = var.enable_waf ? 1 : 0

  source  = "cloudposse/waf/aws"
  version = "1.17.0"

  providers = {
    aws = aws.us_east_1
  }

  # Inherit naming from WAF label
  context = module.waf_label.context

  # CloudFront scope (must be in us-east-1)
  scope = "CLOUDFRONT"

  # Deny-by-default: block all requests that don't match allow rules
  default_action = "block"

  # IP allowlist rule - evaluated first (priority 1)
  ip_set_reference_statement_rules = [
    {
      name     = "allow-whitelisted-ips"
      action   = "allow"
      priority = 1

      # cloudposse/waf module expects 'arn' directly in statement, not nested
      statement = {
        arn = aws_wafv2_ip_set.allowlist[0].arn
      }

      visibility_config = {
        cloudwatch_metrics_enabled = true
        sampled_requests_enabled   = true
        metric_name                = "${module.waf_label.id}-allowlist"
      }
    }
  ]

  # Optional managed rule groups (evaluated after IP allowlist)
  managed_rule_group_statement_rules = [
    for idx, rule in var.waf_managed_rules : {
      name            = rule.name
      priority        = rule.priority
      override_action = "none"

      statement = {
        name        = rule.name
        vendor_name = rule.vendor_name

        # Rule exclusions if specified
        rule_action_override = [
          for excluded_rule in rule.excluded_rules : {
            name          = excluded_rule
            action_to_use = { count = {} }
          }
        ]
      }

      visibility_config = {
        cloudwatch_metrics_enabled = true
        sampled_requests_enabled   = true
        metric_name                = "${module.waf_label.id}-${rule.name}"
      }
    }
  ]

  # Default visibility config for the Web ACL itself
  visibility_config = {
    cloudwatch_metrics_enabled = true
    sampled_requests_enabled   = true
    metric_name                = module.waf_label.id
  }
}
