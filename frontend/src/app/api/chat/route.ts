/**
 * Chat API Route (AI SDK v6)
 *
 * This route handles streaming chat requests from the frontend useChat hook
 * and forwards them to the Strands agent backend deployed on AgentCore Runtime.
 *
 * Uses the Vercel AI SDK v6 patterns:
 * - UIMessage type for messages with parts array
 * - convertToModelMessages() for backend conversion
 * - toUIMessageStreamResponse() for streaming responses
 */

import { NextRequest, NextResponse } from 'next/server'
import { UIMessage, convertToModelMessages } from 'ai'

// === Configuration ===

const AGENT_URL = process.env.AGENT_URL ?? process.env.NEXT_PUBLIC_AGENT_URL ?? ''
const REQUEST_TIMEOUT = 60000 // 60 seconds

// Allow streaming responses up to 60 seconds
export const maxDuration = 60

// === Route Handler ===

export async function POST(request: NextRequest) {
  try {
    // Log request details for debugging
    const contentType = request.headers.get('content-type')
    const contentLength = request.headers.get('content-length')
    console.log(`Chat API: content-type=${contentType}, content-length=${contentLength}`)

    // Check for empty body first - can happen with certain request patterns
    const text = await request.text()
    if (!text || text.trim() === '') {
      console.warn('Chat API received empty request body')
      return NextResponse.json({ error: 'Request body is required' }, { status: 400 })
    }

    console.log(`Chat API: body length=${text.length}, preview=${text.slice(0, 200)}`)

    // Parse request body - AI SDK v6 sends UIMessage[] with parts array
    let body: unknown
    try {
      body = JSON.parse(text)
    } catch {
      console.warn('Chat API received invalid JSON:', text.slice(0, 100))
      return NextResponse.json({ error: 'Invalid JSON in request body' }, { status: 400 })
    }

    const { messages, sessionId }: { messages: UIMessage[]; sessionId?: string } = body as {
      messages: UIMessage[]
      sessionId?: string
    }

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return NextResponse.json({ error: 'Messages array is required' }, { status: 400 })
    }

    // Check if agent URL is configured
    if (!AGENT_URL) {
      console.warn('AGENT_URL not configured, using mock response')
      return createMockStreamResponse(messages)
    }

    // Forward to Strands agent
    return await forwardToAgent(messages, sessionId, request)
  } catch (error) {
    console.error('Chat API error:', error)

    if (error instanceof Error) {
      return NextResponse.json({ error: error.message }, { status: 500 })
    }

    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}

// === Agent Communication ===

async function forwardToAgent(
  messages: UIMessage[],
  sessionId: string | undefined,
  request: NextRequest
): Promise<Response> {
  // Extract auth token from request headers
  const authHeader = request.headers.get('Authorization')

  // Convert UI messages to model messages for the backend
  const modelMessages = await convertToModelMessages(messages)

  // Create abort controller for timeout
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT)

  try {
    const agentResponse = await fetch(`${AGENT_URL}/invoke-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader && { Authorization: authHeader }),
        ...(sessionId && { 'X-Session-Id': sessionId }),
      },
      body: JSON.stringify({ messages: modelMessages }),
      signal: controller.signal,
    })

    clearTimeout(timeoutId)

    if (!agentResponse.ok) {
      const errorText = await agentResponse.text()
      throw new Error(`Agent error: ${agentResponse.status} - ${errorText}`)
    }

    // Stream the response back to the client
    const stream = agentResponse.body

    if (!stream) {
      throw new Error('No response stream from agent')
    }

    // Return streaming response with AI SDK v6 compatible headers
    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    })
  } catch (error) {
    clearTimeout(timeoutId)

    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timeout - the agent took too long to respond')
    }

    throw error
  }
}

// === Mock Response (for development without agent) ===

/**
 * Creates a mock streaming response that mimics the AI SDK v6 UI Message Stream Protocol.
 * This is used when AGENT_URL is not configured for local development.
 *
 * AI SDK v6 uses SSE (Server-Sent Events) format with JSON objects:
 * - data: {"type":"start","messageId":"..."}
 * - data: {"type":"text-start","id":"..."}
 * - data: {"type":"text-delta","id":"...","delta":"..."}
 * - data: {"type":"text-end","id":"..."}
 *
 * @see https://sdk.vercel.ai/docs/ai-sdk-ui/stream-protocol
 */
function createMockStreamResponse(messages: UIMessage[]): Response {
  const lastMessage = messages[messages.length - 1]

  // Extract text from the last message's parts
  const userMessage =
    lastMessage?.parts
      ?.filter((part): part is { type: 'text'; text: string } => part.type === 'text')
      .map((part) => part.text)
      .join(' ') ?? ''

  // Generate a contextual mock response
  const mockResponse = generateMockResponse(userMessage)

  // Create AI SDK v6 compatible SSE stream
  const encoder = new TextEncoder()

  // Generate unique IDs for this response
  const messageId = `msg_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  const textPartId = `text_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`

  // Track stream state and timeouts for cleanup
  let isClosed = false
  let currentTimeoutId: ReturnType<typeof setTimeout> | null = null

  const stream = new ReadableStream({
    start(controller) {
      // Send start event
      const sendSSE = (data: object) => {
        if (isClosed) return false
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`))
          return true
        } catch {
          isClosed = true
          return false
        }
      }

      // 1. Send message start
      if (!sendSSE({ type: 'start', messageId })) return

      // 2. Send text-start
      if (!sendSSE({ type: 'text-start', id: textPartId })) return

      // 3. Stream text deltas
      const words = mockResponse.split(' ')
      let index = 0

      const sendNextChunk = () => {
        if (isClosed) return

        if (index < words.length) {
          const delta = (index === 0 ? '' : ' ') + words[index]
          if (!sendSSE({ type: 'text-delta', id: textPartId, delta })) return
          index++
          currentTimeoutId = setTimeout(sendNextChunk, 30)
        } else {
          // 4. Send text-end
          sendSSE({ type: 'text-end', id: textPartId })

          // 5. Send finish event
          sendSSE({ type: 'finish', finishReason: 'stop' })

          try {
            controller.close()
          } catch {
            // Already closed
          }
          isClosed = true
        }
      }

      // Start streaming after a small delay
      currentTimeoutId = setTimeout(sendNextChunk, 100)
    },
    cancel() {
      isClosed = true
      if (currentTimeoutId) {
        clearTimeout(currentTimeoutId)
      }
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
      'x-vercel-ai-ui-message-stream': 'v1', // Required for AI SDK v6 custom backends
    },
  })
}

function generateMockResponse(userMessage: string): string {
  const lowerMessage = userMessage.toLowerCase()

  // Check for common intents
  if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hola')) {
    return `¡Hola! Welcome to Summerhouse! I'm your booking assistant for our beautiful vacation rental in Quesada, Alicante. How can I help you today? Would you like to check availability, learn about the property, or get information about the Costa Blanca area?`
  }

  if (lowerMessage.includes('availability') || lowerMessage.includes('available')) {
    return `I'd be happy to check availability for you! Our property in Quesada is available for bookings throughout the year. What dates are you considering for your stay? Just let me know your preferred check-in and check-out dates, and I'll confirm availability and provide pricing.`
  }

  if (lowerMessage.includes('price') || lowerMessage.includes('cost') || lowerMessage.includes('rate')) {
    return `Our rates vary by season:\n\n• Low season (Nov-Mar): €80/night, 3-night minimum\n• Mid season (Apr-Jun, Sep-Oct): €100/night, 4-night minimum\n• High season (July): €130/night, 5-night minimum\n• Peak season (August): €150/night, 7-night minimum\n\nAll stays include a €60 cleaning fee. For an accurate quote, just tell me your dates!`
  }

  if (lowerMessage.includes('book') || lowerMessage.includes('reserve')) {
    return `I'd love to help you book your stay at Summerhouse! To get started, I'll need:\n\n1. Your check-in and check-out dates\n2. Number of guests (max 4)\n3. Your email for confirmation\n\nWhat dates work best for you?`
  }

  if (lowerMessage.includes('property') || lowerMessage.includes('apartment') || lowerMessage.includes('house')) {
    return `Summerhouse is a lovely 2-bedroom apartment in Quesada, Alicante. It features:\n\n• 2 comfortable bedrooms (sleeps 4)\n• Full kitchen with modern appliances\n• Private terrace with garden views\n• Air conditioning throughout\n• Free WiFi\n• Communal pool access\n\nIt's perfectly located for exploring the Costa Blanca beaches, golf courses, and local Spanish culture. Would you like to know more about anything specific?`
  }

  if (
    lowerMessage.includes('area') ||
    lowerMessage.includes('quesada') ||
    lowerMessage.includes('alicante')
  ) {
    return `Quesada is a wonderful base for exploring the Costa Blanca! Here are some highlights:\n\n• Beaches: Guardamar and La Mata beaches are 15 minutes away\n• Golf: Multiple courses nearby including La Marquesa and La Finca\n• Culture: Visit historic Orihuela or the caves of Canelobre\n• Dining: Great local tapas bars and restaurants\n\nThe weather is fantastic year-round with over 300 sunny days! Would you like specific recommendations?`
  }

  // Default response
  return `Thanks for your message! I'm the Summerhouse booking assistant, here to help you plan your perfect vacation in Quesada, Alicante. I can help you with:\n\n• Checking availability\n• Getting pricing information\n• Making a reservation\n• Learning about the property\n• Exploring the Costa Blanca area\n\nWhat would you like to know?`
}

// === Health Check ===

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    version: 'ai-sdk-v6',
    agentConfigured: !!AGENT_URL,
    timestamp: new Date().toISOString(),
  })
}
