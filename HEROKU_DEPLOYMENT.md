# Heroku Deployment Guide

This guide explains how to deploy the Open Deep Research agent to Heroku using the Heroku Inference API.

## Prerequisites

1. Heroku account and CLI installed
2. Git repository with the modified code

## Quick Deployment

### 1. Create Heroku App

```bash
heroku create your-app-name
```

### 2. Add Heroku Inference API

```bash
heroku addons:create heroku-inference:claude-4-sonnet --app your-app-name
```

This automatically sets `HEROKU_INFERENCE_API_KEY` and `OPENAI_API_BASE` environment variables.

### 3. Optional: Add Search API Key

For enhanced search capabilities, add Tavily API key:

```bash
heroku config:set TAVILY_API_KEY=your_tavily_key --app your-app-name
```

### 4. Deploy

```bash
git add .
git commit -m "Add Heroku deployment configuration"
git push heroku main
```

## API Endpoints

Once deployed, your app will have the following endpoints:

- `GET /` - Health check
- `GET /health` - Health status
- `POST /research` - Conduct research
- `GET /config` - Get current configuration

### Example Usage

```bash
# Health check
curl https://your-app-name.herokuapp.com/health

# Conduct research
curl -X POST https://your-app-name.herokuapp.com/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the latest developments in AI safety?"}'
```

## Configuration

The app automatically detects Heroku Inference API and configures all models to use `claude-4-sonnet`. You can override this by setting environment variables:

```bash
heroku config:set RESEARCH_MODEL=openai:gpt-4 --app your-app-name
heroku config:set SUMMARIZATION_MODEL=openai:gpt-3.5-turbo --app your-app-name
```

## Environment Variables

### Required (automatically set by addon)
- `HEROKU_INFERENCE_API_KEY` - Set by heroku-inference addon
- `OPENAI_API_BASE` - Set to Heroku's inference endpoint

### Optional
- `TAVILY_API_KEY` - For enhanced web search
- `ANTHROPIC_API_KEY` - For direct Anthropic API access
- `LANGSMITH_API_KEY` - For tracing and monitoring
- `LANGSMITH_PROJECT` - LangSmith project name

## Cost Considerations

The Heroku Inference API addon has different pricing tiers. Monitor your usage:

```bash
heroku addons:info heroku-inference --app your-app-name
```

## Troubleshooting

### Check Logs
```bash
heroku logs --tail --app your-app-name
```

### Verify Environment Variables
```bash
heroku config --app your-app-name
```

### Test the API
```bash
curl https://your-app-name.herokuapp.com/config
```

## Scaling

For high-traffic scenarios, consider scaling:

```bash
heroku ps:scale web=2 --app your-app-name
```

## Local Testing

To test locally with Heroku-like configuration:

1. Copy `.env.heroku` to `.env`
2. Set your API keys
3. Run: `python -m uvicorn src.open_deep_research.server:app --host 0.0.0.0 --port 8000`

## Monitoring

Consider adding these addons for production monitoring:

```bash
heroku addons:create papertrail --app your-app-name
heroku addons:create newrelic --app your-app-name
```