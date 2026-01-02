# Static Website Module - Outputs

output "bucket_name" {
  description = "Name of the S3 bucket hosting the website"
  value       = module.s3_bucket.s3_bucket_id
}

output "bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3_bucket.s3_bucket_arn
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = module.s3_bucket.s3_bucket_bucket_regional_domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = module.cloudfront.cloudfront_distribution_id
}

output "cloudfront_distribution_arn" {
  description = "CloudFront distribution ARN"
  value       = module.cloudfront.cloudfront_distribution_arn
}

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name"
  value       = module.cloudfront.cloudfront_distribution_domain_name
}

output "cloudfront_hosted_zone_id" {
  description = "CloudFront hosted zone ID for Route53 alias"
  value       = module.cloudfront.cloudfront_distribution_hosted_zone_id
}

output "website_url" {
  description = "Full URL of the website"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "https://${module.cloudfront.cloudfront_distribution_domain_name}"
}

output "deploy_command" {
  description = "Command to deploy frontend to S3"
  value       = "aws s3 sync frontend/out/ s3://${module.s3_bucket.s3_bucket_id}/ --delete && aws cloudfront create-invalidation --distribution-id ${module.cloudfront.cloudfront_distribution_id} --paths '/*'"
}

# -----------------------------------------------------------------------------
# WAF Outputs
# -----------------------------------------------------------------------------

output "waf_web_acl_id" {
  description = "WAF Web ACL ID (null if WAF disabled)"
  value       = var.enable_waf ? module.waf[0].id : null
}

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN (null if WAF disabled)"
  value       = var.enable_waf ? module.waf[0].arn : null
}

output "waf_ip_set_arns" {
  description = "WAF IP Set ARNs for whitelisted IPs (null if WAF disabled). Returns object with ipv4 and ipv6 ARNs."
  value = var.enable_waf ? {
    ipv4 = length(aws_wafv2_ip_set.allowlist_ipv4) > 0 ? aws_wafv2_ip_set.allowlist_ipv4[0].arn : null
    ipv6 = length(aws_wafv2_ip_set.allowlist_ipv6) > 0 ? aws_wafv2_ip_set.allowlist_ipv6[0].arn : null
  } : null
}
