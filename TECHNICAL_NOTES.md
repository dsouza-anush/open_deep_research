# Technical Notes for Next Developer

## Overview
This fork implements Heroku deployment with Claude 4 Sonnet via Heroku Inference API and Bright Data for web search. The core functionality is working, but there's a specific tool calling compatibility issue that needs resolution.

## Architecture Changes Made

### 1. Heroku Integration (`src/open_deep_research/server.py`)
```python
# Heroku Inference API Configuration
if os.getenv("INFERENCE_KEY"):
    config_dict.update({
        "research_model": "openai:claude-4-sonnet",
        "summarization_model": "openai:claude-4-sonnet", 
        "compression_model": "openai:claude-4-sonnet",
        "final_report_model": "openai:claude-4-sonnet",
        "search_api": "brightdata",
        "allow_clarification": False  # Disabled for compatibility
    })
```

### 2. Bright Data Integration (`src/open_deep_research/utils.py`)
- Replaced Tavily with Bright Data web scraping API
- Added `langchain-brightdata` package
- Configured API key retrieval from environment

### 3. Structured Output Compatibility (`src/open_deep_research/deep_researcher.py`)
- Added Heroku Inference API detection via model name pattern `openai:`
- Implemented fallback parsing for structured outputs when `response_format` not supported
- **CRITICAL**: Message filtering logic was causing tool calling issues

## Current Issue Analysis

### Problem: `messages[2]: content is required`
**Location**: `src/open_deep_research/deep_researcher.py:336` in `supervisor` function
**Root Cause**: LangChain creates AI message objects with empty content when using tool calls

### Technical Details
1. **Message Flow**: 
   - supervisor → supervisor_tools → supervisor (loop)
   - AI messages with tool calls have content in `tool_calls` field, not `content` field
   - OpenAI API requires all messages to have non-empty content

2. **LangChain Behavior**:
   ```python
   # This creates a message with empty content but tool_calls populated
   AIMessage(content='', tool_calls=[...])
   ```

3. **API Validation**: 
   - Heroku Inference API (OpenAI-compatible) validates message content
   - Empty content fails validation even if tool_calls are present

### Debugging Added
```python
print(f"Debug: Sending {len(supervisor_messages)} messages to supervisor")
print(f"Debug: Adding {len(all_tool_messages)} tool messages")
```

## Attempted Solutions

### ✅ What Works
1. **response_format compatibility** - Structured output fallbacks implemented
2. **Environment variable security** - No hardcoded secrets
3. **Bright Data integration** - Web search functional
4. **UI rendering** - Markdown parsing working

### ❌ What Doesn't Work Yet
1. **Tool calling message validation** - Empty content in AI messages
2. **Supervisor workflow** - Fails on tool call sequences

### 🔄 Solutions Tried
1. **Message filtering** - Removed aggressive filtering that was breaking tool sequences
2. **Content validation** - Added checks but issue persists
3. **Structured output workarounds** - Implemented but doesn't solve message content issue

## Recommended Next Steps

### Option 1: Message Content Patching
```python
# In supervisor function, before API call
for msg in supervisor_messages:
    if hasattr(msg, 'tool_calls') and msg.tool_calls and not msg.content:
        msg.content = "Using tools to process request"
```

### Option 2: Architectural Simplification
- Remove complex supervisor tool calling
- Use direct function calls instead of LangChain tool abstractions
- Implement text-based coordination

### Option 3: LangChain Message Debugging
- Add comprehensive message logging
- Identify exact point where empty content messages are created
- Patch LangChain message construction

## File Structure for Debugging

### Key Files to Investigate
1. `src/open_deep_research/deep_researcher.py:320-350` - Supervisor function
2. `src/open_deep_research/deep_researcher.py:354-475` - Supervisor tools function  
3. `src/open_deep_research/state.py:55-82` - Message state management

### Debugging Commands
```bash
# Deploy changes
git push heroku main

# Test endpoint
curl -X POST "https://open-deep-research-1755945095-d3e3b53f6c8f.herokuapp.com/research" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' 

# View logs
heroku logs --tail --app open-deep-research-1755945095
```

## Integration Status

### ✅ Working Integrations
- Heroku platform deployment
- Heroku Inference API (Claude 4 Sonnet)
- Bright Data API (web search)
- FastAPI + Jinja2 UI
- Environment variable management
- Heroku Button deployment

### ⚠️ Partial Integration
- LangGraph workflow (works until supervisor tool calling)
- Deep research capability (architecture present, tool calling blocks execution)

## Performance Notes
- **Cold start**: ~5-10 seconds for first request
- **Memory usage**: Well within Heroku limits
- **API latency**: Claude 4 Sonnet via Heroku Inference is fast
- **Search performance**: Bright Data provides comprehensive results

## Security Implementation
- All API keys in Heroku config vars
- No secrets in git-tracked code
- Proper HTTPS termination
- Input validation on research queries

The core challenge is purely the LangChain message object validation issue. All other integrations are solid and production-ready.