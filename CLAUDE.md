# Open Deep Research - Heroku Reference App

## Project Description
Open Deep Research is a configurable deep research agent deployed on Heroku with a Chainlit UI. It uses Claude 4 Sonnet via Heroku Inference API for AI-powered research.

## Repository Structure

### Root Directory
- `README.md` - Project documentation with deployment guide
- `pyproject.toml` - Python dependencies
- `langgraph.json` - LangGraph configuration
- `Procfile` - Heroku process definition (runs Chainlit)
- `app.json` - Heroku Button deployment config
- `requirements.txt` - Pip dependencies for Heroku
- `runtime.txt` - Python version for Heroku

### Chainlit UI (`src/open_deep_research/`)
- `chainlit_app.py` - Main Chainlit UI with starters, settings, progress visualization
- `.chainlit/config.toml` - Chainlit configuration (theme, branding)
- `chainlit.md` - Welcome message content
- `public/` - UI assets (icons for starter buttons, logo)

### Core Research Engine
- `deep_researcher.py` - LangGraph research workflow
- `configuration.py` - Configuration management
- `state.py` - Graph state definitions
- `prompts.py` - System prompts
- `utils.py` - Utility functions

### API Server
- `server.py` - FastAPI REST API for programmatic access

### Testing (`tests/`)
- `run_evaluate.py` - Evaluation script for Deep Research Bench
- `evaluators.py` - Evaluation functions

## Key Technologies
- **Chainlit** - Conversational UI framework
- **LangGraph** - Research workflow orchestration
- **LangChain** - LLM integration
- **Heroku Inference API** - Claude 4 Sonnet access
- **Tavily/Bright Data** - Web search APIs

## Development Commands
```bash
# Local development with Chainlit
chainlit run src/open_deep_research/chainlit_app.py -w

# LangGraph Studio
uvx langgraph dev

# Run API server only
uvicorn src.open_deep_research.server:app --reload
```

## Heroku Deployment
The app deploys via Heroku Button with:
- `INFERENCE_KEY` - Heroku Inference API key (auto-provisioned)
- `INFERENCE_URL` - API endpoint (auto-provisioned)
- `TAVILY_API_KEY` - Web search API key (optional)
