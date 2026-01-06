# OTP Interceptor Module - Outputs

output "lambda_function_arn" {
  description = "ARN of the OTP Interceptor Lambda function"
  value       = module.lambda.lambda_function_arn
}

output "lambda_function_name" {
  description = "Name of the OTP Interceptor Lambda function"
  value       = module.lambda.lambda_function_name
}

output "lambda_function_invoke_arn" {
  description = "Invoke ARN of the OTP Interceptor Lambda function (for Cognito trigger)"
  value       = module.lambda.lambda_function_invoke_arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key used by Custom Email Sender (required for Cognito configuration)"
  value       = aws_kms_key.custom_email_sender.arn
}
