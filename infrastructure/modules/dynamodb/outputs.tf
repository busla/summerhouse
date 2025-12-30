# DynamoDB Module Outputs

output "reservations_table_name" {
  description = "Name of the reservations table"
  value       = module.reservations.dynamodb_table_id
}

output "reservations_table_arn" {
  description = "ARN of the reservations table"
  value       = module.reservations.dynamodb_table_arn
}

output "guests_table_name" {
  description = "Name of the guests table"
  value       = module.guests.dynamodb_table_id
}

output "guests_table_arn" {
  description = "ARN of the guests table"
  value       = module.guests.dynamodb_table_arn
}

output "availability_table_name" {
  description = "Name of the availability table"
  value       = module.availability.dynamodb_table_id
}

output "availability_table_arn" {
  description = "ARN of the availability table"
  value       = module.availability.dynamodb_table_arn
}

output "pricing_table_name" {
  description = "Name of the pricing table"
  value       = module.pricing.dynamodb_table_id
}

output "pricing_table_arn" {
  description = "ARN of the pricing table"
  value       = module.pricing.dynamodb_table_arn
}

output "payments_table_name" {
  description = "Name of the payments table"
  value       = module.payments.dynamodb_table_id
}

output "payments_table_arn" {
  description = "ARN of the payments table"
  value       = module.payments.dynamodb_table_arn
}

output "verification_codes_table_name" {
  description = "Name of the verification codes table"
  value       = module.verification_codes.dynamodb_table_id
}

output "verification_codes_table_arn" {
  description = "ARN of the verification codes table"
  value       = module.verification_codes.dynamodb_table_arn
}

output "oauth2_sessions_table_name" {
  description = "Name of the OAuth2 sessions table"
  value       = module.oauth2_sessions.dynamodb_table_id
}

output "oauth2_sessions_table_arn" {
  description = "ARN of the OAuth2 sessions table"
  value       = module.oauth2_sessions.dynamodb_table_arn
}

output "table_arns" {
  description = "List of all table ARNs for IAM policies"
  value = [
    module.reservations.dynamodb_table_arn,
    module.guests.dynamodb_table_arn,
    module.availability.dynamodb_table_arn,
    module.pricing.dynamodb_table_arn,
    module.payments.dynamodb_table_arn,
    module.verification_codes.dynamodb_table_arn,
    module.oauth2_sessions.dynamodb_table_arn,
  ]
}

output "table_prefix" {
  description = "Table name prefix (for DYNAMODB_TABLE_PREFIX env var)"
  value       = module.label.id
}
