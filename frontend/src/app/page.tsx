/**
 * Summerhouse Chat Page
 *
 * Main chat interface for the vacation rental booking assistant.
 * Uses Vercel AI SDK v6 with ai-elements components.
 */

'use client'

import { useChat } from '@ai-sdk/react'
import { DefaultChatTransport } from 'ai'
import { useState, useRef, useCallback } from 'react'
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
  Message,
  MessageContent,
  MessageResponse,
  MessageLoading,
  Input,
  PromptInputTextarea,
  PromptInputSubmit,
  PromptInputWrapper,
} from '@/components/ai-elements'

// === Icons ===

function SunIcon({ className = '' }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="48"
      height="48"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  )
}

// === Chat Page Component ===

export default function ChatPage() {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  // AI SDK v6: input state is now managed separately from useChat
  const [input, setInput] = useState('')

  // AI SDK v6 useChat hook with transport-based architecture
  const { messages, status, error, sendMessage } = useChat({
    transport: new DefaultChatTransport({
      api: '/api/chat',
    }),
  })

  const isLoading = status === 'streaming' || status === 'submitted'

  // Handle form submission - AI SDK v6 pattern
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!input.trim() || isLoading) return

      // Send message - AI SDK v6 uses sendMessage with text
      sendMessage({ text: input })

      setInput('')
      inputRef.current?.focus()
    },
    [input, isLoading, sendMessage]
  )

  // Handle input change
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setInput(e.target.value)
    },
    []
  )

  // Extract text from message parts (v6 format)
  const getMessageText = (message: (typeof messages)[0]): string => {
    // v6 messages have parts array
    if ('parts' in message && Array.isArray(message.parts)) {
      return message.parts
        .filter((part): part is { type: 'text'; text: string } => part.type === 'text')
        .map((part) => part.text)
        .join('')
    }
    // Fallback for content string (backwards compatibility)
    if ('content' in message && typeof message.content === 'string') {
      return message.content
    }
    return ''
  }

  return (
    <div className="chat-page">
      {/* Chat Area */}
      <div className="chat-container max-w-4xl mx-auto w-full">
        <Conversation className="flex-1 flex flex-col">
          <ConversationContent className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 ? (
              <ConversationEmptyState
                icon={<SunIcon className="text-yellow-500" />}
                title="Welcome to Summerhouse!"
                description="I'm your booking assistant for our beautiful vacation rental in Quesada, Alicante. Ask me about availability, pricing, the property, or the local area."
              >
                <div className="mt-4 flex flex-wrap gap-2 justify-center">
                  <SuggestionButton
                    onClick={() => sendMessage({ text: 'What dates are available?' })}
                    label="Check availability"
                  />
                  <SuggestionButton
                    onClick={() => sendMessage({ text: 'How much does it cost to stay?' })}
                    label="See pricing"
                  />
                  <SuggestionButton
                    onClick={() => sendMessage({ text: 'Tell me about the property' })}
                    label="Property details"
                  />
                  <SuggestionButton
                    onClick={() => sendMessage({ text: "What's there to do nearby?" })}
                    label="Local attractions"
                  />
                </div>
              </ConversationEmptyState>
            ) : (
              <>
                {messages.map((message) => (
                  <Message key={message.id} from={message.role as 'user' | 'assistant'}>
                    <MessageContent>
                      {message.role === 'assistant' ? (
                        <MessageResponse>{getMessageText(message)}</MessageResponse>
                      ) : (
                        <span className="whitespace-pre-wrap">{getMessageText(message)}</span>
                      )}
                    </MessageContent>
                  </Message>
                ))}

                {/* Loading indicator */}
                {isLoading && messages[messages.length - 1]?.role === 'user' && (
                  <Message from="assistant">
                    <MessageContent>
                      <MessageLoading />
                    </MessageContent>
                  </Message>
                )}
              </>
            )}
          </ConversationContent>

          <ConversationScrollButton />
        </Conversation>

        {/* Error Display */}
        {error && (
          <div className="px-4 py-2 bg-red-50 border-t border-red-200">
            <p className="text-sm text-red-600">Error: {error.message}</p>
          </div>
        )}

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white p-4">
          <Input onSubmit={handleSubmit}>
            <PromptInputWrapper>
              <PromptInputTextarea
                ref={inputRef}
                value={input}
                onChange={handleInputChange}
                placeholder="Ask about availability, pricing, or the property..."
                disabled={isLoading}
              />
              <PromptInputSubmit
                status={isLoading ? 'streaming' : input.trim() ? 'ready' : 'disabled'}
                disabled={!input.trim() || isLoading}
              />
            </PromptInputWrapper>
          </Input>
          <p className="text-xs text-gray-400 mt-2 text-center">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}

// === Suggestion Button ===

interface SuggestionButtonProps {
  onClick: () => void
  label: string
}

function SuggestionButton({ onClick, label }: SuggestionButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-gray-300 transition-colors"
    >
      {label}
    </button>
  )
}
