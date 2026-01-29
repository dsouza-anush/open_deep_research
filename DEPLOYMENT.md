# Heroku Deployment Guide

This document provides comprehensive guidance for deploying LangGraph applications to Heroku, using this Open Deep Research agent as a reference implementation.

## Quick Deployment (Recommended)

Use the Heroku Button for one-click deployment:

[![Deploy to Heroku](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy?template=https://github.com/dsouza-anush/open_deep_research)

## Manual Deployment

### Prerequisites

1. Heroku CLI installed
2. Git repository
3. Python application ready for deployment

### Step-by-Step Process

#### 1. Create Required Files

**`app.json`** (for Heroku Button support):
```json
{
  "name": "Your App Name",
  "description": "App description",
  "repository": "https://github.com/username/repo",
  "stack": "heroku-24",
  "buildpacks": [{"url": "heroku/python"}],
  "env": {
    "PYTHONPATH": {"value": "/app/src"}
  },
  "addons": [
    {"plan": "heroku-inference:claude-4-sonnet", "as": "INFERENCE"}
  ]
}
```

**`Procfile`**:
```
web: chainlit run src/open_deep_research/chainlit_app.py --host 0.0.0.0 --port $PORT
```

**`runtime.txt`**:
```
python-3.11.0
```

**`requirements.txt`**:
Generate from your dependencies or copy from this project.

#### 2. Deploy via CLI

```bash
# Login to Heroku
heroku login

# Create app
heroku create your-app-name

# Add Heroku Inference addon
heroku addons:create heroku-inference:claude-4-sonnet --app your-app-name

# Set environment variables
heroku config:set PYTHONPATH=/app/src --app your-app-name
heroku config:set OPENAI_API_BASE=https://us.inference.heroku.com/v1 --app your-app-name

# Deploy
git push heroku main
```

## Architecture Decisions

### Single-App Design
- **Pros**: Simple deployment, lower cost, easier maintenance
- **Cons**: All services in one dyno, limited scalability
- **Best for**: MVP, demos, small-scale applications

### Alternative: Microservices
- Separate API and frontend services
- Better scalability but higher complexity and cost
- Requires careful configuration of CORS and service communication

### Database Considerations
- **Stateless**: No database required (current approach)
- **PostgreSQL**: `heroku addons:create heroku-postgresql:mini`
- **Redis**: `heroku addons:create heroku-redis:mini`

## Environment Variables

### Required
- `PYTHONPATH`: Set to `/app/src` for proper imports
- `INFERENCE_KEY`: Automatically set by Heroku Inference addon
- `OPENAI_API_BASE`: Set to Heroku Inference endpoint

### Optional
- `BRIGHTDATA_API_KEY`: For web search and scraping (set this for optimal search functionality)
- `TAVILY_API_KEY`: For fallback web search
- `LANGSMITH_API_KEY`: For tracing and monitoring
- `LANGSMITH_TRACING`: Set to `false` for production

### Setting Environment Variables for Heroku
After deployment, set your Bright Data API key:
```bash
heroku config:set BRIGHTDATA_API_KEY=your_api_key_here --app your-app-name
```

## Cost Optimization

### Dyno Types
- **Basic ($7/month)**: Always-on, good for production
- **Eco ($5/month)**: Sleeps after 30min inactivity
- **Free**: Deprecated, not recommended

### Scaling Strategies
1. **Vertical**: Upgrade dyno type (Standard-1X, Standard-2X)
2. **Horizontal**: `heroku ps:scale web=2`
3. **Auto-scaling**: Configure based on metrics

### Cost Monitoring
```bash
# Check current usage
heroku ps --app your-app-name

# Monitor addon costs
heroku addons:info heroku-inference --app your-app-name

# View billing
heroku billing
```

## Production Considerations

### Security
- Use environment variables for all secrets
- Enable HTTPS (automatic on Heroku)
- Implement rate limiting if needed
- Validate all user inputs

### Monitoring
- Add logging: `heroku logs --tail --app your-app-name`
- Consider New Relic: `heroku addons:create newrelic`
- Set up alerts for errors and performance

### Performance
- Enable gzip compression in FastAPI
- Add caching headers for static assets
- Monitor response times and optimize accordingly

### Error Handling
- Implement comprehensive error handling
- Use structured logging
- Set up error reporting (e.g., Sentry)

## Troubleshooting

### Common Issues

**Build Failures**:
- Check Python version in runtime.txt
- Verify requirements.txt dependencies
- Review build logs: `heroku logs --app your-app-name`

**Runtime Errors**:
- Check application logs
- Verify environment variables
- Test locally first

**Performance Issues**:
- Monitor dyno metrics
- Check database connection pooling
- Optimize heavy operations

### Debug Commands
```bash
# Check app status
heroku ps --app your-app-name

# View recent logs
heroku logs --tail --num 100 --app your-app-name

# Run one-off commands
heroku run python --app your-app-name

# Access bash shell
heroku run bash --app your-app-name
```

## Advanced Features

### Custom Domains
```bash
heroku domains:add www.yourdomain.com --app your-app-name
```

### SSL Certificates
- Automatic for *.herokuapp.com domains
- Custom domains: `heroku certs:auto:enable --app your-app-name`

### Review Apps
- Configure in `app.json` for automatic PR deployments
- Great for testing and collaboration

### Pipeline Deployment
- Set up staging → production pipeline
- Automatic promotions based on CI/CD

## Reference Links

- [Heroku Python Documentation](https://devcenter.heroku.com/categories/python-support)
- [Heroku Button Documentation](https://devcenter.heroku.com/articles/heroku-button)
- [Heroku Inference API](https://devcenter.heroku.com/articles/heroku-inference-api-v1-chat-completions)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/heroku/)

This deployment serves as a complete reference for modern Python web application deployment on Heroku with AI integration.