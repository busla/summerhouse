# Quickstart Guide: Static Website WAF Protection

**Feature**: 002-static-website-waf
**Date**: 2025-12-29

## Prerequisites

### Required Tools

| Tool | Version | Installation |
|------|---------|--------------|
| Terraform | 1.5+ | `brew install terraform` |
| Task | 3.x | `brew install go-task` or [taskfile.dev](https://taskfile.dev) |
| AWS CLI | 2.x | `brew install awscli` |

### AWS Permissions

Your AWS credentials must have permissions for:
- WAF (Web ACL, IP Sets, Rules)
- CloudFront (modify distribution for WAF attachment)

## Quick Usage

### 1. Enable WAF (Default Configuration)

WAF is enabled by default with IP `157.157.199.250` whitelisted. No changes needed for basic protection.

```bash
# From repo root - verify plan shows WAF resources
task tf:plan:dev

# Apply to enable WAF
task tf:apply:dev
```

### 2. Add Additional IPs

Modify your environment's tfvars to whitelist more IPs:

**File**: `infrastructure/environments/dev/terraform.tfvars.json`

```json
{
  "waf_whitelisted_ips": [
    {
      "ip": "157.157.199.250/32",
      "description": "Primary trusted access IP"
    },
    {
      "ip": "203.0.113.50/32",
      "description": "Developer home office"
    },
    {
      "ip": "198.51.100.0/24",
      "description": "Office network CIDR"
    }
  ]
}
```

```bash
task tf:apply:dev
```

### 3. Disable WAF

To disable WAF protection entirely:

```json
{
  "enable_waf": false
}
```

```bash
task tf:apply:dev
```

### 4. Add Managed Rules (Optional)

For additional protection beyond IP allowlisting:

```json
{
  "waf_managed_rules": [
    {
      "name": "AWSManagedRulesCommonRuleSet",
      "vendor_name": "AWS",
      "priority": 10,
      "excluded_rules": []
    }
  ]
}
```

## Verification

### Test Whitelisted Access

From a whitelisted IP:

```bash
curl -I https://your-site.example.com
# Expected: HTTP 200 OK
```

### Test Blocked Access

From a non-whitelisted IP:

```bash
curl -I https://your-site.example.com
# Expected: HTTP 403 Forbidden
```

### Check WAF Status in AWS Console

1. Go to AWS WAF & Shield console
2. Select **us-east-1** region (required for CloudFront WAF)
3. Click **Web ACLs** → Find your ACL (named `booking-{env}-website-*`)
4. Verify **Associated AWS resources** shows your CloudFront distribution

### View Terraform Outputs

```bash
task tf:output:dev

# Shows:
# waf_web_acl_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# waf_web_acl_arn = "arn:aws:wafv2:us-east-1:123456789012:global/webacl/..."
# waf_ip_set_arn = "arn:aws:wafv2:us-east-1:123456789012:global/ipset/..."
```

## Configuration Reference

### Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `enable_waf` | bool | `true` | Enable/disable WAF |
| `waf_whitelisted_ips` | list(object) | `[{ip="157.157.199.250/32", description="Primary..."}]` | IPs to whitelist |
| `waf_managed_rules` | list(object) | `[]` | Optional AWS managed rules |

### IP Format Requirements

- Must be in CIDR notation
- IPv4: `x.x.x.x/32` for single IP, `x.x.x.x/24` for subnet
- IPv6: `xxxx:xxxx::/128` for single IP

### Available Managed Rule Groups

| Rule Group | Description |
|------------|-------------|
| `AWSManagedRulesCommonRuleSet` | General OWASP Top 10 protection |
| `AWSManagedRulesKnownBadInputsRuleSet` | Known malicious inputs |
| `AWSManagedRulesSQLiRuleSet` | SQL injection protection |
| `AWSManagedRulesLinuxRuleSet` | Linux-specific attacks |
| `AWSManagedRulesAmazonIpReputationList` | IP reputation filtering |

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| WAF not attaching to CloudFront | Wrong region | WAF must be in us-east-1 for CloudFront |
| All requests blocked (403) | IP not in allowlist | Add your IP to `waf_whitelisted_ips` |
| Invalid CIDR error | Wrong IP format | Use `/32` suffix for single IPs |
| WAF creation fails | Missing permissions | Ensure IAM has `waf:*` permissions |

### Check Your Public IP

```bash
curl -4 ifconfig.me
# Returns your IPv4 address - add /32 suffix for CIDR
```

### View WAF Metrics

In AWS Console:
1. Go to CloudWatch → Metrics → WAF
2. Select your Web ACL
3. View `BlockedRequests` and `AllowedRequests` metrics

### Debug with AWS CLI

```bash
# List WAF Web ACLs in us-east-1 (CLOUDFRONT scope)
aws wafv2 list-web-acls --scope CLOUDFRONT --region us-east-1

# Get Web ACL details
aws wafv2 get-web-acl \
  --scope CLOUDFRONT \
  --region us-east-1 \
  --name "booking-dev-website" \
  --id "your-web-acl-id"

# List IP Sets
aws wafv2 list-ip-sets --scope CLOUDFRONT --region us-east-1
```

## Security Notes

### Deny-by-Default Model

This WAF implements strict deny-by-default:
- **ONLY** IPs in `waf_whitelisted_ips` can access the site
- All other requests receive **403 Forbidden**
- No managed rules are enabled by default

### Important Considerations

1. **Empty allowlist = site inaccessible**: If you accidentally remove all IPs from `waf_whitelisted_ips`, the site becomes completely inaccessible
2. **CIDR ranges**: Be careful with large CIDR ranges (e.g., `/8`) as they allow many IPs
3. **IPv6 support**: The module supports both IPv4 and IPv6 addresses
4. **Description field**: The `description` field is for documentation only—use it to identify IP owners

## Sample Configurations

### Development (Relaxed)

```json
{
  "enable_waf": true,
  "waf_whitelisted_ips": [
    {"ip": "157.157.199.250/32", "description": "Primary trusted IP"},
    {"ip": "10.0.0.0/8", "description": "All private networks (dev only)"}
  ]
}
```

### Production (Strict)

```json
{
  "enable_waf": true,
  "waf_whitelisted_ips": [
    {"ip": "157.157.199.250/32", "description": "Primary trusted IP"},
    {"ip": "203.0.113.10/32", "description": "CI/CD server"}
  ],
  "waf_managed_rules": [
    {
      "name": "AWSManagedRulesCommonRuleSet",
      "vendor_name": "AWS",
      "priority": 10,
      "excluded_rules": []
    },
    {
      "name": "AWSManagedRulesKnownBadInputsRuleSet",
      "vendor_name": "AWS",
      "priority": 20,
      "excluded_rules": []
    }
  ]
}
```

### WAF Disabled

```json
{
  "enable_waf": false
}
```

## Next Steps

After WAF is deployed:

1. **Verify access** from your whitelisted IP
2. **Test blocking** from a non-whitelisted IP (use mobile data or VPN)
3. **Monitor metrics** in CloudWatch for blocked requests
4. **Add managed rules** if additional protection is needed

## Resources

- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/latest/developerguide/)
- [cloudposse/waf/aws Module](https://registry.terraform.io/modules/cloudposse/waf/aws/latest)
- [AWS Managed Rules Groups](https://docs.aws.amazon.com/waf/latest/developerguide/aws-managed-rule-groups-list.html)
- [CloudFront WAF Integration](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-awswaf.html)
