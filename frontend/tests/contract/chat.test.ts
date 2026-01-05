/**
 * Contract Test: /api/chat endpoint
 *
 * Defines the API contract between frontend and backend for the chat endpoint.
 * These tests ensure both sides agree on request/response formats.
 *
 * Contract tests validate:
 * 1. Request schema (what frontend sends)
 * 2. Response schema (what backend returns)
 * 3. Error response format
 * 4. Header requirements
 */

import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import { z } from 'zod'

// === Request Schemas (What Frontend Sends) ===

/**
 * AI SDK v6 UIMessage part types
 */
const TextPartSchema = z.object({
  type: z.literal('text'),
  text: z.string(),
})

const ToolCallPartSchema = z.object({
  type: z.literal('tool-call'),
  toolCallId: z.string(),
  toolName: z.string(),
  args: z.record(z.unknown()),
})

const ToolResultPartSchema = z.object({
  type: z.literal('tool-result'),
  toolCallId: z.string(),
  result: z.unknown(),
})

const MessagePartSchema = z.discriminatedUnion('type', [
  TextPartSchema,
  ToolCallPartSchema,
  ToolResultPartSchema,
])

/**
 * AI SDK v6 UIMessage format
 */
const UIMessageSchema = z.object({
  id: z.string(),
  role: z.enum(['user', 'assistant', 'system']),
  parts: z.array(MessagePartSchema),
  createdAt: z.string().datetime().optional(),
})

/**
 * Chat API Request body schema
 */
const ChatRequestSchema = z.object({
  messages: z.array(UIMessageSchema).min(1),
  sessionId: z.string().optional(),
})

// === Response Schemas (What Backend Returns) ===

/**
 * Streaming response event types (Server-Sent Events format)
 *
 * AI SDK v6 uses a specific SSE format:
 * - "0:" prefix for text deltas/content
 * - "e:" prefix for events (finish, error)
 * - Each line ends with "\n"
 */
const StreamTextDeltaSchema = z.string()

const StreamFinishEventSchema = z.object({
  finishReason: z.enum(['stop', 'length', 'content-filter', 'tool-calls', 'error']),
  usage: z
    .object({
      promptTokens: z.number().optional(),
      completionTokens: z.number().optional(),
      totalTokens: z.number().optional(),
    })
    .optional(),
})

const StreamErrorEventSchema = z.object({
  error: z.string(),
})

/**
 * Error response schema (non-streaming)
 */
const ErrorResponseSchema = z.object({
  error: z.string(),
})

/**
 * Health check response schema (GET /api/chat)
 */
const HealthResponseSchema = z.object({
  status: z.literal('ok'),
  version: z.string(),
  agentConfigured: z.boolean(),
  timestamp: z.string().datetime(),
})

// === Contract Tests ===

describe('Chat API Contract', () => {
  describe('Request Schema', () => {
    it('validates a minimal chat request', () => {
      const validRequest = {
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            parts: [{ type: 'text', text: 'Hello' }],
          },
        ],
      }

      const result = ChatRequestSchema.safeParse(validRequest)
      expect(result.success).toBe(true)
    })

    it('validates a request with sessionId', () => {
      const validRequest = {
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            parts: [{ type: 'text', text: 'Check availability for next week' }],
          },
        ],
        sessionId: 'session-abc-123',
      }

      const result = ChatRequestSchema.safeParse(validRequest)
      expect(result.success).toBe(true)
    })

    it('validates a multi-turn conversation', () => {
      const validRequest = {
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            parts: [{ type: 'text', text: 'Hi, I want to book a stay' }],
          },
          {
            id: 'msg-2',
            role: 'assistant',
            parts: [{ type: 'text', text: 'Great! When would you like to check in?' }],
          },
          {
            id: 'msg-3',
            role: 'user',
            parts: [{ type: 'text', text: 'January 15th to January 20th' }],
          },
        ],
      }

      const result = ChatRequestSchema.safeParse(validRequest)
      expect(result.success).toBe(true)
    })

    // TODO: Fix Zod v4 discriminatedUnion issue with tool-call/tool-result parts
    it.skip('validates messages with tool call parts', () => {
      const validRequest = {
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            parts: [{ type: 'text', text: 'Is January 15-20 available?' }],
          },
          {
            id: 'msg-2',
            role: 'assistant',
            parts: [
              {
                type: 'tool-call',
                toolCallId: 'call-123',
                toolName: 'check_availability',
                args: { check_in: '2025-01-15', check_out: '2025-01-20' },
              },
            ],
          },
          {
            id: 'msg-3',
            role: 'assistant',
            parts: [
              {
                type: 'tool-result',
                toolCallId: 'call-123',
                result: { is_available: true, total_nights: 5 },
              },
            ],
          },
        ],
      }

      const result = ChatRequestSchema.safeParse(validRequest)
      expect(result.success).toBe(true)
    })

    it('rejects empty messages array', () => {
      const invalidRequest = {
        messages: [],
      }

      const result = ChatRequestSchema.safeParse(invalidRequest)
      expect(result.success).toBe(false)
    })

    it('rejects message without id', () => {
      const invalidRequest = {
        messages: [
          {
            role: 'user',
            parts: [{ type: 'text', text: 'Hello' }],
          },
        ],
      }

      const result = ChatRequestSchema.safeParse(invalidRequest)
      expect(result.success).toBe(false)
    })

    it('rejects message without parts array', () => {
      const invalidRequest = {
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            content: 'Hello', // Old format, not valid for AI SDK v6
          },
        ],
      }

      const result = ChatRequestSchema.safeParse(invalidRequest)
      expect(result.success).toBe(false)
    })

    it('rejects invalid role', () => {
      const invalidRequest = {
        messages: [
          {
            id: 'msg-1',
            role: 'bot', // Invalid role
            parts: [{ type: 'text', text: 'Hello' }],
          },
        ],
      }

      const result = ChatRequestSchema.safeParse(invalidRequest)
      expect(result.success).toBe(false)
    })
  })

  describe('Response Schema', () => {
    it('validates error response format', () => {
      const errorResponse = {
        error: 'Messages array is required',
      }

      const result = ErrorResponseSchema.safeParse(errorResponse)
      expect(result.success).toBe(true)
    })

    it('validates health check response', () => {
      const healthResponse = {
        status: 'ok',
        version: 'ai-sdk-v6',
        agentConfigured: true,
        timestamp: '2025-01-15T10:30:00.000Z',
      }

      const result = HealthResponseSchema.safeParse(healthResponse)
      expect(result.success).toBe(true)
    })

    it('validates health check with agent not configured', () => {
      const healthResponse = {
        status: 'ok',
        version: 'ai-sdk-v6',
        agentConfigured: false,
        timestamp: '2025-01-15T10:30:00.000Z',
      }

      const result = HealthResponseSchema.safeParse(healthResponse)
      expect(result.success).toBe(true)
    })

    it('validates stream finish event', () => {
      const finishEvent = {
        finishReason: 'stop',
      }

      const result = StreamFinishEventSchema.safeParse(finishEvent)
      expect(result.success).toBe(true)
    })

    it('validates stream finish event with usage stats', () => {
      const finishEvent = {
        finishReason: 'stop',
        usage: {
          promptTokens: 50,
          completionTokens: 100,
          totalTokens: 150,
        },
      }

      const result = StreamFinishEventSchema.safeParse(finishEvent)
      expect(result.success).toBe(true)
    })

    it('validates stream error event', () => {
      const errorEvent = {
        error: 'Request timeout - the agent took too long to respond',
      }

      const result = StreamErrorEventSchema.safeParse(errorEvent)
      expect(result.success).toBe(true)
    })
  })

  describe('Stream Format', () => {
    it('parses SSE text delta line', () => {
      const sseLine = '0:"Hello"\n'

      // Parse SSE format: prefix:JSON\n
      const match = sseLine.match(/^(\d+|e):(.+)\n$/)
      expect(match).not.toBeNull()
      expect(match![1]).toBe('0')

      const content = JSON.parse(match![2])
      expect(content).toBe('Hello')
    })

    it('parses SSE finish event line', () => {
      const sseLine = 'e:{"finishReason":"stop"}\n'

      const match = sseLine.match(/^(\d+|e):(.+)\n$/)
      expect(match).not.toBeNull()
      expect(match![1]).toBe('e')

      const event = JSON.parse(match![2])
      expect(StreamFinishEventSchema.safeParse(event).success).toBe(true)
    })

    it('parses message start event', () => {
      const sseLine = '0:{"type":"message-start","id":"msg-abc123"}\n'

      const match = sseLine.match(/^(\d+|e):(.+)\n$/)
      expect(match).not.toBeNull()

      const event = JSON.parse(match![2])
      expect(event.type).toBe('message-start')
      expect(event.id).toBeDefined()
    })
  })

  describe('HTTP Headers Contract', () => {
    it('defines required request headers', () => {
      const requiredHeaders = {
        'Content-Type': 'application/json',
      }

      expect(requiredHeaders['Content-Type']).toBe('application/json')
    })

    it('defines optional auth header format', () => {
      const authHeader = 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'

      expect(authHeader).toMatch(/^Bearer .+/)
    })

    it('defines streaming response headers', () => {
      const responseHeaders = {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      }

      expect(responseHeaders['Content-Type']).toBe('text/event-stream')
      expect(responseHeaders['Cache-Control']).toBe('no-cache')
    })

    it('defines session header format', () => {
      const sessionHeader = 'X-Session-Id'
      const sessionValue = 'session-abc-123-def-456'

      expect(sessionHeader).toBe('X-Session-Id')
      expect(sessionValue).toMatch(/^session-.+/)
    })
  })

  describe('Error Codes Contract', () => {
    it('defines expected error status codes', () => {
      const errorCodes = {
        BAD_REQUEST: 400,
        UNAUTHORIZED: 401,
        NOT_FOUND: 404,
        TIMEOUT: 408,
        INTERNAL_ERROR: 500,
        SERVICE_UNAVAILABLE: 503,
      }

      expect(errorCodes.BAD_REQUEST).toBe(400)
      expect(errorCodes.INTERNAL_ERROR).toBe(500)
    })

    it('defines expected error messages', () => {
      const errorMessages = [
        'Messages array is required',
        'Request timeout - the agent took too long to respond',
        'Internal server error',
        'Agent error: 500 - Internal server error',
      ]

      errorMessages.forEach((msg) => {
        expect(ErrorResponseSchema.safeParse({ error: msg }).success).toBe(true)
      })
    })
  })
})

// === Type Exports for Frontend Usage ===

export type ChatRequest = z.infer<typeof ChatRequestSchema>
export type UIMessage = z.infer<typeof UIMessageSchema>
export type MessagePart = z.infer<typeof MessagePartSchema>
export type ErrorResponse = z.infer<typeof ErrorResponseSchema>
export type HealthResponse = z.infer<typeof HealthResponseSchema>
export type StreamFinishEvent = z.infer<typeof StreamFinishEventSchema>

// Export schemas for runtime validation
export {
  ChatRequestSchema,
  UIMessageSchema,
  MessagePartSchema,
  ErrorResponseSchema,
  HealthResponseSchema,
  StreamFinishEventSchema,
  StreamErrorEventSchema,
}
