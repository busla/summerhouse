/**
 * Custom Chat Hook for AgentCore Runtime (Browser Direct)
 *
 * This hook provides a useChat-like interface for direct browser-to-AgentCore
 * communication using SigV4 signing with Cognito Identity Pool credentials.
 *
 * Why this exists:
 * - Next.js static export (output: 'export') doesn't include API routes
 * - The frontend is hosted on S3/CloudFront as static files
 * - All dynamic functionality must happen client-side
 * - We use Cognito Identity Pool for anonymous AWS credentials
 *
 * This replaces the AI SDK's useChat hook which requires a backend API route.
 */

'use client'

import { useState, useCallback, useRef } from 'react'
import { invokeAgentCore, type AgentResponse } from '@/lib/sigv4-fetch'
import { isTokenDeliveryEvent, sessionFromTokenEvent, storeSession } from '@/lib/auth'

// === Types ===

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  /** Text content (for backwards compatibility) */
  content: string
  /** AI SDK v6 parts format */
  parts: Array<{ type: 'text'; text: string }>
  /** ISO timestamp */
  createdAt: Date
}

export type ChatStatus = 'idle' | 'submitted' | 'streaming' | 'error'

export interface UseAgentChatOptions {
  /** Initial messages to populate the chat */
  initialMessages?: ChatMessage[]
  /** Callback when an error occurs */
  onError?: (error: Error) => void
  /** Callback when a response is received */
  onResponse?: (response: AgentResponse) => void
}

export interface UseAgentChatReturn {
  /** All messages in the conversation */
  messages: ChatMessage[]
  /** Current chat status */
  status: ChatStatus
  /** Error if any occurred */
  error: Error | null
  /** Send a new message */
  sendMessage: (message: { text: string }) => Promise<void>
  /** Clear all messages and start fresh */
  clearMessages: () => void
  /** Reset error state */
  clearError: () => void
}

// === Helper Functions ===

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
}

function createMessage(role: 'user' | 'assistant', text: string): ChatMessage {
  return {
    id: generateId(),
    role,
    content: text,
    parts: [{ type: 'text', text }],
    createdAt: new Date(),
  }
}

// === Hook Implementation ===

/**
 * Custom hook for direct browser-to-AgentCore chat.
 *
 * Provides a similar interface to AI SDK's useChat but calls AgentCore
 * directly from the browser using SigV4 signing.
 *
 * @example
 * ```tsx
 * import { useAgentChat } from '@/hooks/useAgentChat'
 *
 * function Chat() {
 *   const { messages, status, error, sendMessage } = useAgentChat()
 *
 *   const handleSend = () => {
 *     sendMessage({ text: 'What dates are available?' })
 *   }
 * }
 * ```
 */
export function useAgentChat(options: UseAgentChatOptions = {}): UseAgentChatReturn {
  const { initialMessages = [], onError, onResponse } = options

  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<Error | null>(null)

  // Store session ID for conversation continuity
  const sessionIdRef = useRef<string | undefined>(undefined)

  // Prevent concurrent requests
  const isProcessingRef = useRef(false)

  const sendMessage = useCallback(
    async (message: { text: string }) => {
      const userText = message.text.trim()
      if (!userText || isProcessingRef.current) return

      isProcessingRef.current = true
      setError(null)
      setStatus('submitted')

      // Add user message immediately for responsive UI
      const userMessage = createMessage('user', userText)

      // Create placeholder assistant message for streaming
      const assistantMessageId = generateId()
      const assistantMessage: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        parts: [{ type: 'text', text: '' }],
        createdAt: new Date(),
      }

      // Add both messages - user + empty assistant placeholder
      setMessages((prev) => [...prev, userMessage, assistantMessage])

      try {
        setStatus('streaming')

        // Call AgentCore with streaming callback for real-time updates
        const response = await invokeAgentCore({
          message: userText,
          sessionId: sessionIdRef.current,
          timeout: 60000,
          // Real-time streaming: update assistant message as chunks arrive
          onChunk: (chunk: string) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMessageId
                  ? {
                      ...msg,
                      content: msg.content + chunk,
                      parts: [{ type: 'text', text: msg.content + chunk }],
                    }
                  : msg
              )
            )
          },
        })

        // Store session ID for conversation continuity
        if (response.sessionId) {
          sessionIdRef.current = response.sessionId
        }

        // T025: Check tool results for TokenDeliveryEvent and store session
        if (response.toolResults) {
          for (const result of response.toolResults) {
            if (isTokenDeliveryEvent(result)) {
              const session = sessionFromTokenEvent(result)
              storeSession(session)
              // T026: Log token delivery (without exposing token values)
              console.log('[Auth] Session stored after token delivery', {
                guestId: session.guestId,
                email: session.email,
                expiresAt: session.expiresAt,
              })
            }
          }
        }

        // Finalize the assistant message with complete text
        // (in case any chunks were missed or for consistency)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: response.text,
                  parts: [{ type: 'text', text: response.text }],
                }
              : msg
          )
        )

        setStatus('idle')
        onResponse?.(response)
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Failed to send message')
        setError(error)
        setStatus('error')
        onError?.(error)

        // Update the assistant message to show error
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: msg.content || 'Sorry, an error occurred. Please try again.',
                  parts: [
                    {
                      type: 'text',
                      text: msg.content || 'Sorry, an error occurred. Please try again.',
                    },
                  ],
                }
              : msg
          )
        )

        // Log for debugging
        console.error('AgentCore invocation failed:', error)
      } finally {
        isProcessingRef.current = false
      }
    },
    [onError, onResponse]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    sessionIdRef.current = undefined
    setError(null)
    setStatus('idle')
  }, [])

  const clearError = useCallback(() => {
    setError(null)
    if (status === 'error') {
      setStatus('idle')
    }
  }, [status])

  return {
    messages,
    status,
    error,
    sendMessage,
    clearMessages,
    clearError,
  }
}

export default useAgentChat
