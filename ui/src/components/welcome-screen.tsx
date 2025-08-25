import React from 'react'
import { Search, Zap, Globe, Brain } from 'lucide-react'

export function WelcomeScreen() {
  const features = [
    {
      icon: Brain,
      title: "AI-Powered Analysis",
      description: "Advanced research using Claude 4 Sonnet for comprehensive analysis and synthesis"
    },
    {
      icon: Search,
      title: "Deep Web Research",
      description: "Access current information through enterprise-grade web scraping and search APIs"
    },
    {
      icon: Zap,
      title: "Real-time Progress",
      description: "Live updates on research progress with streaming report generation"
    },
    {
      icon: Globe,
      title: "Multi-Source Verification",
      description: "Cross-reference information from multiple sources for accuracy and completeness"
    }
  ]

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="mb-8 animate-in fade-in duration-1000">
        <h1 className="text-4xl font-bold mb-4 bg-gradient-to-r from-primary via-blue-600 to-purple-600 bg-clip-text text-transparent">
          Open Deep Research
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Comprehensive AI-powered research agent that analyzes multiple sources to provide detailed, 
          accurate reports on any topic you need to explore.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 max-w-4xl animate-in slide-in-from-bottom duration-1000 delay-200">
        {features.map((feature, index) => (
          <div
            key={feature.title}
            className="bg-card border border-border rounded-lg p-6 hover:shadow-lg transition-all duration-200 hover:border-primary/20"
            style={{ animationDelay: `${300 + index * 100}ms` }}
          >
            <feature.icon className="w-8 h-8 text-primary mx-auto mb-3" />
            <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
            <p className="text-muted-foreground text-sm leading-relaxed">{feature.description}</p>
          </div>
        ))}
      </div>

      <div className="text-muted-foreground text-sm animate-in fade-in duration-1000 delay-800">
        <p className="mb-2">Start by asking a research question below</p>
        <p className="text-xs opacity-75">
          Example: "Research the latest developments in renewable energy technology"
        </p>
      </div>
    </div>
  )
}