import React from 'react'
import { Button } from '@/components/ui/button'
import { cn, formatDate } from '@/lib/utils'
import { Plus, Menu, Trash2 } from 'lucide-react'
import type { Chat } from '@/lib/types'

interface SidebarProps {
  chats: Chat[]
  currentChatId: string | null
  isOpen: boolean
  onToggle: () => void
  onNewChat: () => void
  onSelectChat: (chatId: string) => void
  onDeleteChat: (chatId: string) => void
}

export function Sidebar({
  chats,
  currentChatId,
  isOpen,
  onToggle,
  onNewChat,
  onSelectChat,
  onDeleteChat
}: SidebarProps) {
  const sortedChats = [...chats].sort((a, b) => 
    new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
  )

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/20 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}
      
      {/* Sidebar */}
      <div className={cn(
        "fixed left-0 top-0 z-50 h-full w-80 bg-sidebar-background border-r border-sidebar-border transform transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0",
        isOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-sidebar-border">
            <h1 className="text-lg font-semibold text-sidebar-foreground">
              Deep Research
            </h1>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={onNewChat}
                className="text-sidebar-foreground hover:bg-sidebar-accent"
              >
                <Plus className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggle}
                className="text-sidebar-foreground hover:bg-sidebar-accent lg:hidden"
              >
                <Menu className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {/* Chat list */}
          <div className="flex-1 overflow-y-auto p-2">
            {sortedChats.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sidebar-foreground/60 text-sm mb-4">
                  No conversations yet
                </p>
                <Button
                  variant="outline"
                  onClick={onNewChat}
                  className="text-sm"
                >
                  Start your first research
                </Button>
              </div>
            ) : (
              <div className="space-y-1">
                {sortedChats.map((chat) => (
                  <div
                    key={chat.id}
                    className={cn(
                      "group relative flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors",
                      "hover:bg-sidebar-accent",
                      currentChatId === chat.id 
                        ? "bg-sidebar-accent border-l-2 border-sidebar-primary" 
                        : ""
                    )}
                    onClick={() => onSelectChat(chat.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <h3 className={cn(
                        "text-sm font-medium truncate",
                        currentChatId === chat.id
                          ? "text-sidebar-foreground"
                          : "text-sidebar-foreground/80"
                      )}>
                        {chat.title}
                      </h3>
                      <div className="flex items-center gap-2 mt-1">
                        <p className="text-xs text-sidebar-foreground/60">
                          {chat.messages.length} message{chat.messages.length !== 1 ? 's' : ''}
                        </p>
                        <span className="text-sidebar-foreground/40">•</span>
                        <p className="text-xs text-sidebar-foreground/60">
                          {formatDate(chat.updatedAt)}
                        </p>
                      </div>
                    </div>

                    {/* Delete button */}
                    {chats.length > 1 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="opacity-0 group-hover:opacity-100 h-6 w-6 text-sidebar-foreground/60 hover:text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteChat(chat.id)
                        }}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-sidebar-border">
            <div className="text-xs text-sidebar-foreground/60 text-center">
              Powered by Claude 4 Sonnet & Bright Data
            </div>
          </div>
        </div>
      </div>
    </>
  )
}