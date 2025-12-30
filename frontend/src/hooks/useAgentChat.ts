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

import { useState, useCallback, useRef, useEffect } from 'react'
import { invokeAgentCore, type AgentResponse } from '@/lib/sigv4-fetch'
import { ensureValidIdToken } from '@/lib/auth'
import type { AuthRequiredEvent } from '@/types'

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
  /**
   * Callback when auth is required (from @requires_access_token tools).
   * The consumer should redirect to login with the auth_url.
   */
  onAuthRequired?: (event: AuthRequiredEvent) => void
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

/**
 * Detect auth redirect marker in streaming text.
 *
 * Following AgentCore samples pattern: auth URLs are embedded in text
 * with the format [AUTH_REDIRECT:url]. This allows the frontend to detect
 * when authentication is required and redirect automatically.
 *
 * @param text - Text to search for auth redirect marker
 * @returns The auth URL if found, null otherwise
 */
function extractAuthRedirectUrl(text: string): string | null {
  const match = text.match(/\[AUTH_REDIRECT:([^\]]+)\]/)
  return match?.[1] ?? null
}

/**
 * Strip auth redirect marker from text for display.
 * Users shouldn't see the raw marker in the chat UI.
 */
function stripAuthRedirectMarker(text: string): string {
  return text.replace(/\[AUTH_REDIRECT:[^\]]+\]/, '').trim()
}

// === Conversation Persistence ===

const CONVERSATION_STORAGE_KEY = 'booking_conversation'

interface PersistedConversation {
  messages: ChatMessage[]
  sessionId: string | undefined
  timestamp: number
}

/**
 * Save conversation state to sessionStorage.
 * Used before auth redirect to preserve conversation across navigation.
 */
function saveConversation(messages: ChatMessage[], sessionId: string | undefined): void {
  if (typeof window === 'undefined') return
  const data: PersistedConversation = {
    messages,
    sessionId,
    timestamp: Date.now(),
  }
  sessionStorage.setItem(CONVERSATION_STORAGE_KEY, JSON.stringify(data))
}

/**
 * Load conversation state from sessionStorage.
 * Returns null if no saved conversation or if it's stale (>1 hour).
 */
function loadConversation(): PersistedConversation | null {
  if (typeof window === 'undefined') return null
  try {
    const stored = sessionStorage.getItem(CONVERSATION_STORAGE_KEY)
    if (!stored) return null

    const data: PersistedConversation = JSON.parse(stored)

    // Check if conversation is stale (more than 1 hour old)
    const maxAge = 60 * 60 * 1000 // 1 hour
    if (Date.now() - data.timestamp > maxAge) {
      sessionStorage.removeItem(CONVERSATION_STORAGE_KEY)
      return null
    }

    // Restore Date objects (JSON.parse converts them to strings)
    data.messages = data.messages.map((msg) => ({
      ...msg,
      createdAt: new Date(msg.createdAt),
    }))

    return data
  } catch {
    return null
  }
}

/**
 * Clear persisted conversation from sessionStorage.
 */
function clearPersistedConversation(): void {
  if (typeof window === 'undefined') return
  sessionStorage.removeItem(CONVERSATION_STORAGE_KEY)
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
  const { initialMessages = [], onError, onResponse, onAuthRequired } = options

  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [status, setStatus] = useState<ChatStatus>('idle')
  const [error, setError] = useState<Error | null>(null)

  // Store session ID for conversation continuity
  const sessionIdRef = useRef<string | undefined>(undefined)

  // Prevent concurrent requests
  const isProcessingRef = useRef(false)

  // Track if we've restored conversation (to prevent double-restore)
  const hasRestoredRef = useRef(false)

  // Restore conversation from sessionStorage on mount
  useEffect(() => {
    if (hasRestoredRef.current) return
    hasRestoredRef.current = true

    const persisted = loadConversation()
    if (persisted && persisted.messages.length > 0) {
      console.log('[Chat] Restoring conversation from sessionStorage', {
        messageCount: persisted.messages.length,
        sessionId: persisted.sessionId,
      })
      setMessages(persisted.messages)
      sessionIdRef.current = persisted.sessionId
      // Clear the persisted data after restoring
      clearPersistedConversation()
    }
  }, [])

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

        // Get current auth token (if user is logged in) for authenticated requests
        // This enables backend to identify the user via token's `sub` claim
        const authToken = await ensureValidIdToken()

        // Call AgentCore with streaming callback for real-time updates
        const response = await invokeAgentCore({
          message: userText,
          sessionId: sessionIdRef.current,
          timeout: 60000,
          authToken, // Include for authenticated requests, null for anonymous
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

        // Check for auth redirect marker in response text (AgentCore samples pattern)
        // Tools that require auth return text with [AUTH_REDIRECT:url] embedded
        const authRedirectUrl = extractAuthRedirectUrl(response.text)
        let displayText = response.text

        if (authRedirectUrl) {
          console.log('[Auth] Auth redirect detected in response text')
          // Strip marker from display text so users see clean message
          displayText = stripAuthRedirectMarker(response.text)

          // Save conversation before redirect so it can be restored after login
          // Build the complete conversation with user message and assistant response
          const conversationToSave: ChatMessage[] = [
            ...messages, // Previous messages (from closure, ok since we add new ones below)
            userMessage,
            {
              ...assistantMessage,
              content: displayText,
              parts: [{ type: 'text' as const, text: displayText }],
            },
          ]
          saveConversation(conversationToSave, sessionIdRef.current)
          console.log('[Auth] Conversation saved before auth redirect', {
            messageCount: conversationToSave.length,
          })

          // Construct AuthRequiredEvent and notify consumer
          const authEvent: AuthRequiredEvent = {
            status: 'auth_required',
            auth_url: authRedirectUrl,
            message: displayText,
            action: 'redirect_to_auth',
          }
          onAuthRequired?.(authEvent)
        }

        // Finalize the assistant message with display text (marker stripped if present)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessageId
              ? {
                  ...msg,
                  content: displayText,
                  parts: [{ type: 'text', text: displayText }],
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
    [messages, onError, onResponse, onAuthRequired]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    sessionIdRef.current = undefined
    setError(null)
    setStatus('idle')
    // Clear any persisted conversation
    clearPersistedConversation()
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
