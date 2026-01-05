# Static Website Module - Variables
# S3 + CloudFront for Next.js static export hosting
# Uses cloudposse/label/null context pattern - receives context from root module

variable "context" {
  type = any
  default = {
    enabled             = true
    namespace           = null
    tenant              = null
    environment         = null
    stage               = null
    name                = null
    delimiter           = null
    attributes          = []
    tags                = {}
    additional_tag_map  = {}
    regex_replace_chars = null
    label_order         = []
    id_length_limit     = null
    label_key_case      = null
    label_value_case    = null
    descriptor_formats  = {}
    labels_as_tags      = ["unset"]
  }
  description = <<-EOT
    Single object for setting entire context at once.
    See description of individual variables for details.
    Leave string and numeric variables as `null` to use default value.
    Individual variable settings (non-null) override settings in context object,
    except for attributes, tags, and additional_tag_map, which are merged.
  EOT

  validation {
    condition     = lookup(var.context, "label_key_case", null) == null ? true : contains(["lower", "title", "upper"], var.context["label_key_case"])
    error_message = "Allowed values: `lower`, `title`, `upper`."
  }

  validation {
    condition     = lookup(var.context, "label_value_case", null) == null ? true : contains(["lower", "title", "upper", "none"], var.context["label_value_case"])
    error_message = "Allowed values: `lower`, `title`, `upper`, `none`."
  }
}

variable "domain_name" {
  description = "Custom domain name for the website (e.g., booking.example.com)"
  type        = string
}

variable "certificate_arn" {
  description = "ARN of ACM certificate for HTTPS (must be in us-east-1 for CloudFront)"
  type        = string
}

variable "frontend_build_dir" {
  description = "Path to the Next.js static export directory (frontend/out)"
  type        = string
  default     = null
}

variable "index_document" {
  description = "Index document for the website"
  type        = string
  default     = "index.html"
}

variable "error_document" {
  description = "Error document for 404 pages"
  type        = string
  default     = "404.html"
}

variable "price_class" {
  description = "CloudFront price class"
  type        = string
  default     = "PriceClass_100" # US, Canada, Europe
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID for DNS records. If empty, no DNS records are created."
  type        = string
  default     = ""
}

variable "create_route53_records" {
  description = "Whether to create Route53 A/AAAA records pointing to CloudFront"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# WAF Variables
# -----------------------------------------------------------------------------

variable "enable_waf" {
  description = "Enable WAF protection for CloudFront distribution"
  type        = bool
  default     = true
}

variable "waf_whitelisted_ips" {
  description = "List of IP addresses to whitelist. Each entry requires IP in CIDR notation and a description for documentation clarity."
  type = list(object({
    ip          = string
    description = string
  }))
  default = []

  validation {
    condition = alltrue([
      for entry in var.waf_whitelisted_ips :
      can(cidrhost(entry.ip, 0))
    ])
    error_message = "All IP addresses must be in valid CIDR notation (e.g., 192.168.1.1/32 or 2001:db8::/32)."
  }
}

variable "waf_managed_rules" {
  description = "List of AWS Managed Rule Groups to include. Empty by default (IP allowlist is primary protection)."
  type = list(object({
    name           = string
    vendor_name    = string
    priority       = number
    excluded_rules = optional(list(string), [])
  }))
  default = []
}

variable "waf_allow_api_paths" {
  description = "Allow requests to /api/* paths without IP whitelisting. API has its own Cognito authorizer."
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# API Gateway Origin Variables
# -----------------------------------------------------------------------------

variable "api_gateway_url" {
  description = "API Gateway URL to add as origin for /api/* routes (e.g., https://abc123.execute-api.eu-west-1.amazonaws.com)"
  type        = string
  default     = null
}

variable "api_path_pattern" {
  description = "Path pattern for API Gateway origin (default: /api/*)"
  type        = string
  default     = "/api/*"
}
