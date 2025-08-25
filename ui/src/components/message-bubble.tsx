import React, { useState } from 'react'
import { Button } from '@/components/ui/button'
import { cn, formatTime } from '@/lib/utils'
import { Copy, Check, User, Bot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import type { Message } from '@/lib/types'

interface MessageBubbleProps {
  message: Message
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy text:', error)
    }
  }

  const isLongContent = message.content.length > 200

  return (
    <div className={cn(
      "flex gap-4 group",
      isUser && "flex-row-reverse"
    )}>
      {/* Avatar */}
      <div className={cn(
        "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
        isUser 
          ? "bg-primary text-primary-foreground" 
          : "bg-muted border border-border"
      )}>
        {isUser ? (
          <User className="w-4 h-4" />
        ) : (
          <Bot className="w-4 h-4" />
        )}
      </div>

      {/* Message Content */}
      <div className={cn(
        "flex-1 max-w-[85%]",
        isUser && "flex justify-end"
      )}>
        <div className={cn(
          "relative rounded-2xl px-4 py-3 text-sm",
          isUser ? [
            "bg-primary text-primary-foreground",
            "rounded-br-md"
          ] : [
            "bg-muted border border-border",
            "rounded-bl-md"
          ]
        )}>
          {/* Copy button */}
          <Button
            variant="ghost"
            size="icon"
            className={cn(
              "absolute top-2 right-2 w-6 h-6 opacity-0 group-hover:opacity-100 transition-opacity",
              isUser 
                ? "text-primary-foreground/70 hover:text-primary-foreground hover:bg-white/10" 
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
            onClick={handleCopy}
          >
            {copied ? (
              <Check className="w-3 h-3" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </Button>

          {/* Message text */}
          {!isUser && isLongContent ? (
            <div className="prose prose-sm dark:prose-invert max-w-none pr-8">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  h1: ({ children }) => (
                    <h1 className="text-primary text-xl font-bold mb-4 pb-2 border-b border-border">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-blue-600 dark:text-blue-400 text-lg font-semibold mb-3 mt-6">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-amber-600 dark:text-amber-400 text-base font-semibold mb-2 mt-4">
                      {children}
                    </h3>
                  ),
                  h4: ({ children }) => (
                    <h4 className="text-red-600 dark:text-red-400 text-sm font-semibold mb-2 mt-3">
                      {children}
                    </h4>
                  ),
                  p: ({ children }) => (
                    <p className="mb-3 last:mb-0 leading-relaxed text-foreground">
                      {children}
                    </p>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside mb-3 space-y-1 text-foreground">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside mb-3 space-y-1 text-foreground">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li className="text-foreground">
                      {children}
                    </li>
                  ),
                  strong: ({ children }) => (
                    <strong className="text-primary font-semibold">
                      {children}
                    </strong>
                  ),
                  em: ({ children }) => (
                    <em className="text-muted-foreground italic">
                      {children}
                    </em>
                  ),
                  code: ({ children, className }) => {
                    const isInline = !className
                    return isInline ? (
                      <code className="bg-accent text-accent-foreground px-1.5 py-0.5 rounded text-xs font-mono">
                        {children}
                      </code>
                    ) : (
                      <code className={className}>
                        {children}
                      </code>
                    )
                  },
                  pre: ({ children }) => (
                    <pre className="bg-accent border border-border rounded-lg p-3 overflow-x-auto text-xs font-mono mb-3">
                      {children}
                    </pre>
                  ),
                  blockquote: ({ children }) => (
                    <blockquote className="border-l-4 border-primary bg-accent/50 pl-4 py-2 mb-3 rounded-r italic">
                      {children}
                    </blockquote>
                  ),
                  table: ({ children }) => (
                    <div className="overflow-x-auto mb-3">
                      <table className="min-w-full border border-border rounded-lg">
                        {children}
                      </table>
                    </div>
                  ),
                  th: ({ children }) => (
                    <th className="border-b border-border bg-accent px-3 py-2 text-left font-semibold text-xs">
                      {children}
                    </th>
                  ),
                  td: ({ children }) => (
                    <td className="border-b border-border px-3 py-2 text-xs">
                      {children}
                    </td>
                  )
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            <div className="whitespace-pre-wrap pr-8">
              {message.content}
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div className={cn(
          "text-xs text-muted-foreground mt-1 px-1",
          isUser && "text-right"
        )}>
          {formatTime(message.createdAt)}
        </div>
      </div>
    </div>
  )
}