import React, { useState, useRef, useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { MessageBubble } from '@/components/message-bubble'
import { WelcomeScreen } from '@/components/welcome-screen'
import { ResearchProgress } from '@/components/research-progress'
import { cn, generateId } from '@/lib/utils'
import { Menu, Send, Loader2 } from 'lucide-react'
import type { Chat as ChatType, Message, ResearchJob } from '@/lib/types'

interface ChatProps {
  chat: ChatType | undefined
  onAddMessage: (chatId: string, message: Message) => void
  onToggleSidebar: () => void
  sidebarOpen: boolean
}

export function Chat({ chat, onAddMessage, onToggleSidebar, sidebarOpen }: ChatProps) {
  const [input, setInput] = useState('')
  const [isResearching, setIsResearching] = useState(false)
  const [researchProgress, setResearchProgress] = useState<string>('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [chat?.messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || !chat || isResearching) return

    const userMessage: Message = {
      id: generateId(),
      role: 'user',
      content: input.trim(),
      createdAt: new Date()
    }

    onAddMessage(chat.id, userMessage)
    setInput('')
    setIsResearching(true)
    setResearchProgress('Starting research...')

    try {
      // Start research job
      const response = await fetch('/research/async', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: input.trim() })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      
      if (data.status === 'pending' && data.job_id) {
        // Poll for results
        await pollResearchStatus(data.job_id, chat.id)
      } else {
        throw new Error(data.message || 'Failed to start research')
      }
    } catch (error) {
      console.error('Error starting research:', error)
      
      const errorMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: `Error starting research: ${error instanceof Error ? error.message : 'Unknown error'}`,
        createdAt: new Date()
      }
      
      onAddMessage(chat.id, errorMessage)
      setIsResearching(false)
      setResearchProgress('')
    }
  }

  const pollResearchStatus = async (jobId: string, chatId: string) => {
    const maxAttempts = 300 // 5 minutes max polling
    let attempts = 0
    
    const poll = async (): Promise<void> => {
      if (attempts >= maxAttempts) {
        const timeoutMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: 'Research is taking longer than expected. Please try again with a more specific query.',
          createdAt: new Date()
        }
        onAddMessage(chatId, timeoutMessage)
        setIsResearching(false)
        setResearchProgress('')
        return
      }

      try {
        const response = await fetch(`/research/status/${jobId}`)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const status: ResearchJob = await response.json()
        
        // Update progress
        setResearchProgress(status.progress || 'Researching...')
        
        if (status.status === 'completed') {
          const assistantMessage: Message = {
            id: generateId(),
            role: 'assistant',
            content: status.result || 'Research completed but no report was generated.',
            createdAt: new Date()
          }
          onAddMessage(chatId, assistantMessage)
          setIsResearching(false)
          setResearchProgress('')
          return
          
        } else if (status.status === 'failed') {
          const errorMessage: Message = {
            id: generateId(),
            role: 'assistant',
            content: `Research failed: ${status.error || 'Unknown error occurred'}`,
            createdAt: new Date()
          }
          onAddMessage(chatId, errorMessage)
          setIsResearching(false)
          setResearchProgress('')
          return
        }
        
        // Continue polling
        attempts++
        setTimeout(poll, 1000) // Poll every second
        
      } catch (error) {
        console.error('Error polling research status:', error)
        
        const errorMessage: Message = {
          id: generateId(),
          role: 'assistant',
          content: `Error checking research status: ${error instanceof Error ? error.message : 'Unknown error'}`,
          createdAt: new Date()
        }
        onAddMessage(chatId, errorMessage)
        setIsResearching(false)
        setResearchProgress('')
      }
    }

    poll()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as any)
    }
  }

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`
    }
  }, [input])

  const hasMessages = chat && chat.messages.length > 0

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-3">
          {!sidebarOpen && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onToggleSidebar}
              className="lg:hidden"
            >
              <Menu className="h-4 w-4" />
            </Button>
          )}
          <h2 className="font-semibold text-lg">
            {chat?.title || 'Deep Research'}
          </h2>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-4 py-6">
          {!hasMessages ? (
            <WelcomeScreen />
          ) : (
            <>
              <div className="space-y-6">
                {chat!.messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
              </div>
              
              {isResearching && (
                <div className="mt-6">
                  <ResearchProgress 
                    status={isResearching ? 'in_progress' : 'idle'}
                    progress={researchProgress}
                  />
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="max-w-4xl mx-auto p-4">
          <form onSubmit={handleSubmit} className="relative">
            <div className="flex items-end gap-3 p-3 bg-muted rounded-2xl border border-input focus-within:border-ring">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  isResearching 
                    ? "Research in progress..." 
                    : "Ask me to research any topic..."
                }
                disabled={isResearching}
                className={cn(
                  "flex-1 bg-transparent text-foreground placeholder-muted-foreground resize-none outline-none",
                  "min-h-[20px] max-h-[150px] py-1",
                  isResearching && "opacity-50 cursor-not-allowed"
                )}
                rows={1}
              />
              
              <Button
                type="submit"
                size="icon"
                disabled={isResearching || !input.trim()}
                className="rounded-full w-8 h-8 flex-shrink-0"
              >
                {isResearching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}