import React, { useState } from 'react'
import { Chat } from '@/components/chat'
import { Sidebar } from '@/components/sidebar'
import { useLocalStorage } from '@/hooks/use-local-storage'
import type { Message, Chat as ChatType } from '@/lib/types'

function App() {
  const [chats, setChats] = useLocalStorage<ChatType[]>('chats', [])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useLocalStorage('sidebar-open', true)

  const currentChat = chats.find(chat => chat.id === currentChatId)

  const createNewChat = () => {
    const newChat: ChatType = {
      id: `chat-${Date.now()}`,
      title: 'New Research Session',
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date()
    }
    setChats(prev => [newChat, ...prev])
    setCurrentChatId(newChat.id)
  }

  const updateChat = (chatId: string, updates: Partial<ChatType>) => {
    setChats(prev => prev.map(chat => 
      chat.id === chatId 
        ? { ...chat, ...updates, updatedAt: new Date() }
        : chat
    ))
  }

  const deleteChat = (chatId: string) => {
    setChats(prev => prev.filter(chat => chat.id !== chatId))
    if (currentChatId === chatId) {
      setCurrentChatId(null)
    }
  }

  const addMessage = (chatId: string, message: Message) => {
    const chat = chats.find(c => c.id === chatId)
    if (!chat) return

    const updatedMessages = [...chat.messages, message]
    
    // Update title from first user message
    let title = chat.title
    if (chat.messages.length === 0 && message.role === 'user') {
      title = message.content.slice(0, 50) + (message.content.length > 50 ? '...' : '')
    }

    updateChat(chatId, { 
      messages: updatedMessages,
      title
    })
  }

  // Create initial chat if none exist
  React.useEffect(() => {
    if (chats.length === 0) {
      createNewChat()
    } else if (!currentChatId) {
      setCurrentChatId(chats[0].id)
    }
  }, [chats.length, currentChatId])

  return (
    <div className="flex h-screen bg-background">
      <Sidebar
        chats={chats}
        currentChatId={currentChatId}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onNewChat={createNewChat}
        onSelectChat={setCurrentChatId}
        onDeleteChat={deleteChat}
      />
      
      <main className="flex-1 flex flex-col min-w-0">
        <Chat
          chat={currentChat}
          onAddMessage={addMessage}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          sidebarOpen={sidebarOpen}
        />
      </main>
    </div>
  )
}

export default App