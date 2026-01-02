/**
 * AI Agent Chat Page (/agent)
 *
 * Main chat interface for the vacation rental booking assistant.
 * Uses direct browser-to-AgentCore communication via SigV4 signing.
 *
 * Architecture Note:
 * Since this is a static export (S3 + CloudFront), there are no API routes.
 * The browser calls AgentCore Runtime directly using Cognito Identity Pool
 * credentials for anonymous IAM authentication.
 *
 * Requirements: FR-020, FR-021, FR-022, FR-023
 */

import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Chat with Our AI Concierge | Quesada Apartment',
  description:
    'Get instant answers about availability, pricing, and local attractions. Our AI booking assistant is available 24/7 to help plan your perfect Costa Blanca getaway.',
}

// Re-export the ChatPage component as default
// The actual component is in a separate file to allow 'use client' directive
export { default } from './ChatPage'
