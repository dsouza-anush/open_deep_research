import React from 'react'
import { cn } from '@/lib/utils'
import { Search, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

interface ResearchProgressProps {
  status: 'idle' | 'pending' | 'in_progress' | 'completed' | 'failed'
  progress?: string
}

const statusConfig = {
  pending: {
    icon: Search,
    label: 'Starting Research',
    color: 'text-blue-600',
    bgColor: 'bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800'
  },
  in_progress: {
    icon: FileText,
    label: 'Research in Progress',
    color: 'text-amber-600',
    bgColor: 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800'
  },
  completed: {
    icon: CheckCircle,
    label: 'Research Complete',
    color: 'text-emerald-600',
    bgColor: 'bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800'
  },
  failed: {
    icon: AlertCircle,
    label: 'Research Failed',
    color: 'text-red-600',
    bgColor: 'bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800'
  },
  idle: {
    icon: Search,
    label: 'Ready',
    color: 'text-muted-foreground',
    bgColor: 'bg-muted'
  }
}

export function ResearchProgress({ status, progress }: ResearchProgressProps) {
  const config = statusConfig[status]
  const IconComponent = config.icon

  if (status === 'idle' || status === 'completed') {
    return null
  }

  return (
    <div className={cn(
      "flex items-start gap-4 p-4 rounded-lg border animate-in slide-in-from-top duration-300",
      config.bgColor
    )}>
      {/* Animated Icon */}
      <div className="flex-shrink-0 relative">
        <div className={cn("w-8 h-8 flex items-center justify-center rounded-full", config.color)}>
          {status === 'pending' || status === 'in_progress' ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <IconComponent className="w-5 h-5" />
          )}
        </div>
        
        {/* Pulse effect for active states */}
        {(status === 'pending' || status === 'in_progress') && (
          <div className={cn(
            "absolute inset-0 rounded-full opacity-20 animate-ping",
            config.color.replace('text-', 'bg-')
          )} />
        )}
      </div>

      {/* Progress Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h3 className={cn("font-medium text-sm", config.color)}>
            {config.label}
          </h3>
          {(status === 'pending' || status === 'in_progress') && (
            <div className="flex gap-1">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className={cn("w-1 h-1 rounded-full animate-pulse", config.color.replace('text-', 'bg-'))}
                  style={{ 
                    animationDelay: `${i * 0.2}s`,
                    animationDuration: '1s'
                  }}
                />
              ))}
            </div>
          )}
        </div>
        
        {progress && (
          <p className="text-sm text-muted-foreground">
            {progress}
          </p>
        )}

        {/* Progress Bar */}
        {(status === 'pending' || status === 'in_progress') && (
          <div className="mt-3 h-1 bg-background rounded-full overflow-hidden">
            <div 
              className={cn(
                "h-full rounded-full transition-all duration-1000 ease-out",
                config.color.replace('text-', 'bg-')
              )}
              style={{ 
                width: status === 'pending' ? '30%' : '70%',
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}