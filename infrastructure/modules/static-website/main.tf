# Static Website Module - Main Resources
# Hosts Next.js static export via S3 + CloudFront
#
# Architecture:
# - S3 bucket with private access (no public access)
# - CloudFront distribution with Origin Access Control (OAC)
# - Custom domain with ACM certificate
# - Configured for SPA routing (errors -> index.html)
#
# Pattern: Single label module with context from root

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = ">= 5.0"
      configuration_aliases = [aws.us_east_1]
    }
  }
}

# -----------------------------------------------------------------------------
# CloudPosse Label - inherits context from root, sets component name
# -----------------------------------------------------------------------------

module "label" {
  source  = "cloudposse/label/null"
  version = "~> 0.25"

  # Inherit namespace, environment, tags from root context
  context = var.context

  # Component name for this module
  name = "website"
}

locals {
  s3_origin_id  = "${module.label.id}-s3-origin"
  api_origin_id = "${module.label.id}-api-origin"

  # Parse API Gateway domain from URL (e.g., "https://abc123.execute-api.eu-west-1.amazonaws.com/api")
  # REST API URLs include stage path (/api), HTTP API URLs don't - we need just the domain
  # Regex extracts domain between protocol and first slash/end: "https://domain/path" -> "domain"
  api_gateway_domain = var.api_gateway_url != null ? regex("^https?://([^/]+)", var.api_gateway_url)[0] : null
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# S3 Bucket for Static Files (using terraform-aws-modules/s3-bucket)
# -----------------------------------------------------------------------------

module "s3_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 5.0"

  bucket = module.label.id

  # Versioning
  versioning = {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption_configuration = {
    rule = {
      apply_server_side_encryption_by_default = {
        sse_algorithm = "AES256"
      }
    }
  }

  # Block all public access - CloudFront uses OAC
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true

  # Bucket policy for CloudFront OAC
  attach_policy = true
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontOAC"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "arn:aws:s3:::${module.label.id}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = module.cloudfront.cloudfront_distribution_arn
          }
        }
      }
    ]
  })

  # Object ownership
  control_object_ownership = true
  object_ownership         = "BucketOwnerEnforced"

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# CloudFront Distribution (using terraform-aws-modules/cloudfront)
# -----------------------------------------------------------------------------

module "cloudfront" {
  source  = "terraform-aws-modules/cloudfront/aws"
  version = "~> 6.0"

  aliases             = var.domain_name != "" ? [var.domain_name] : []
  comment             = "${module.label.id} static website"
  enabled             = true
  is_ipv6_enabled     = true
  price_class         = var.price_class
  default_root_object = var.index_document

  # Don't wait for distribution deployment - speeds up terraform apply
  wait_for_deployment = false

  # CloudFront Function for URL rewrite (T012)
  # Normalizes URLs to index.html for Next.js static exports with trailingSlash: true
  cloudfront_functions = {
    url-rewrite = {
      runtime = "cloudfront-js-2.0"
      comment = "Normalize URLs to index.html for Next.js static site"
      code    = file("${path.module}/functions/url-rewrite.js")
      publish = true
    }
  }

  # Origin Access Control for S3
  origin_access_control = {
    s3_oac = {
      description      = "OAC for ${module.label.id}"
      origin_type      = "s3"
      signing_behavior = "always"
      signing_protocol = "sigv4"
    }
  }

  # Origins: S3 for static files, optionally API Gateway for /api/*
  origin = merge(
    {
      s3_origin = {
        domain_name               = module.s3_bucket.s3_bucket_bucket_regional_domain_name
        origin_access_control_key = "s3_oac"
      }
    },
    var.api_gateway_url != null ? {
      api_origin = {
        domain_name = local.api_gateway_domain
        custom_origin_config = {
          http_port              = 80
          https_port             = 443
          origin_protocol_policy = "https-only"
          origin_ssl_protocols   = ["TLSv1.2"]
        }
      }
    } : {}
  )

  # Default cache behavior
  default_cache_behavior = {
    target_origin_id       = "s3_origin"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods  = ["GET", "HEAD"]
    compress        = true

    # Use forwarded_values for simple static content (legacy but explicit control)
    forwarded_values = {
      query_string = false
      cookies = {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600  # 1 hour
    max_ttl     = 86400 # 24 hours

    # CloudFront Function association for URL rewrite (T013)
    # Runs on viewer-request to normalize URLs before S3 lookup
    function_association = {
      viewer-request = {
        function_key = "url-rewrite"
      }
    }
  }

  # Cache behaviors: API Gateway (no cache) + static assets (long cache)
  ordered_cache_behavior = concat(
    # API Gateway behavior (if configured) - must come before S3 behaviors
    var.api_gateway_url != null ? [
      {
        path_pattern           = var.api_path_pattern
        target_origin_id       = "api_origin"
        viewer_protocol_policy = "redirect-to-https"

        allowed_methods = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
        cached_methods  = ["GET", "HEAD"]
        compress        = true

        # Forward all headers/cookies/query strings for API calls (no caching)
        # Must use nested forwarded_values block per terraform-aws-modules/cloudfront syntax
        forwarded_values = {
          query_string = true
          cookies = {
            forward = "all"
          }
          headers = ["Authorization", "Origin", "Accept", "Content-Type"]
        }

        min_ttl     = 0
        default_ttl = 0
        max_ttl     = 0
      }
    ] : [],
    # Static assets behavior (long cache)
    [
      {
        path_pattern           = "_next/static/*"
        target_origin_id       = "s3_origin"
        viewer_protocol_policy = "redirect-to-https"

        allowed_methods = ["GET", "HEAD"]
        cached_methods  = ["GET", "HEAD"]
        compress        = true

        forwarded_values = {
          query_string = false
          cookies = {
            forward = "none"
          }
        }

        min_ttl     = 0
        default_ttl = 31536000 # 1 year
        max_ttl     = 31536000
      }
    ]
  )

  # Error pages: Serve proper error pages with correct status codes
  # Note: With Next.js static export + trailingSlash, all routes are physical files
  # so we don't need SPA-style 404 → index.html fallback.
  # S3 with OAC returns 403 for both missing files AND WAF blocks.
  custom_error_response = [
    {
      error_code            = 403
      response_code         = 403
      response_page_path    = "/403.html"
      error_caching_min_ttl = 10
    },
    {
      error_code            = 404
      response_code         = 404
      response_page_path    = "/404.html"
      error_caching_min_ttl = 10
    }
  ]

  # No geo restrictions
  restrictions = {
    geo_restriction = {
      restriction_type = "none"
      locations        = []
    }
  }

  # SSL/TLS certificate
  viewer_certificate = var.certificate_arn != "" ? {
    acm_certificate_arn      = var.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
    } : {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1"
  }

  # WAF Web ACL attachment (if enabled)
  web_acl_id = var.enable_waf ? module.waf[0].arn : null

  tags = module.label.tags
}

# -----------------------------------------------------------------------------
# Route53 DNS Records (alias to CloudFront)
# -----------------------------------------------------------------------------

# A record (IPv4) pointing to CloudFront
resource "aws_route53_record" "a" {
  count = var.create_route53_records && var.hosted_zone_id != "" && var.domain_name != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = module.cloudfront.cloudfront_distribution_domain_name
    zone_id                = module.cloudfront.cloudfront_distribution_hosted_zone_id
    evaluate_target_health = false
  }
}

# AAAA record (IPv6) pointing to CloudFront
resource "aws_route53_record" "aaaa" {
  count = var.create_route53_records && var.hosted_zone_id != "" && var.domain_name != "" ? 1 : 0

  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "AAAA"

  alias {
    name                   = module.cloudfront.cloudfront_distribution_domain_name
    zone_id                = module.cloudfront.cloudfront_distribution_hosted_zone_id
    evaluate_target_health = false
  }
}

# -----------------------------------------------------------------------------
# Frontend Build and Deploy
# -----------------------------------------------------------------------------

# Build the frontend (Next.js static export)
resource "terraform_data" "frontend_build" {
  count = var.frontend_build_dir != null ? 1 : 0

  triggers_replace = {
    # Hash ALL frontend files except generated directories (node_modules, .next, out, .yarn)
    # fileset excludes directories by not matching them - we only match actual source files
    frontend_hash = sha256(join("", [
      for f in sort(setunion(
        # Source code
        fileset("${var.frontend_build_dir}/..", "src/**/*"),
        # Config files in root
        fileset("${var.frontend_build_dir}/..", "*.{json,js,mjs,ts,cjs,yaml,yml}"),
        # Public assets
        fileset("${var.frontend_build_dir}/..", "public/**/*"),
      )) :
      filesha256("${var.frontend_build_dir}/../${f}")
    ]))
    bucket = module.s3_bucket.s3_bucket_id
  }

  provisioner "local-exec" {
    working_dir = "${var.frontend_build_dir}/.."
    command     = "yarn install && yarn build"
  }
}

# Sync to S3 and invalidate CloudFront
resource "terraform_data" "frontend_deploy" {
  count = var.frontend_build_dir != null ? 1 : 0

  triggers_replace = {
    build_id        = terraform_data.frontend_build[0].id
    distribution_id = module.cloudfront.cloudfront_distribution_id
  }

  provisioner "local-exec" {
    command = "aws s3 sync ${var.frontend_build_dir} s3://${module.s3_bucket.s3_bucket_id}/ --delete && aws cloudfront create-invalidation --distribution-id ${module.cloudfront.cloudfront_distribution_id} --paths '/*'"
  }

  depends_on = [terraform_data.frontend_build]
}
