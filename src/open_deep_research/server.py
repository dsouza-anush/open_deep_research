"""FastAPI server for deploying Deep Research agent to Heroku."""

import os
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration

app = FastAPI(
    title="Open Deep Research API",
    description="Deep research agent with automated report generation",
    version="0.0.16"
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ResearchRequest(BaseModel):
    """Request model for research endpoint."""
    query: str
    config: Optional[Dict] = None

class ResearchResponse(BaseModel):
    """Response model for research endpoint."""
    success: bool
    report: Optional[str] = None
    error: Optional[str] = None

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the web interface."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/research", response_model=ResearchResponse)
async def conduct_research(request: ResearchRequest):
    """Conduct deep research and generate a report."""
    try:
        # Create configuration with Heroku-specific settings
        config_dict = request.config or {}
        
        # Use Heroku Inference API if available
        if os.getenv("INFERENCE_KEY"):
            config_dict.update({
                "research_model": "openai:claude-4-sonnet",
                "summarization_model": "openai:claude-4-sonnet", 
                "compression_model": "openai:claude-4-sonnet",
                "final_report_model": "openai:claude-4-sonnet"
            })
        
        # For now, let's test with a simple OpenAI call
        from langchain.chat_models import init_chat_model
        
        # Get API key and base URL for Heroku Inference
        api_key = os.getenv("INFERENCE_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        
        if not api_key:
            return ResearchResponse(
                success=False,
                error="No API key configured. Please set INFERENCE_KEY or OPENAI_API_KEY."
            )
        
        # Initialize the chat model directly
        model = init_chat_model(
            model="openai:claude-4-sonnet",
            api_key=api_key,
            base_url=base_url,
            max_tokens=4000
        )
        
        # Simple research prompt
        prompt = f"""You are a research assistant. Provide a comprehensive analysis of the following topic:

{request.query}

Please provide:
1. Overview of the topic
2. Key points and findings
3. Current status or recent developments
4. Relevant implications

Keep the response informative and well-structured."""

        # Get response from the model
        response = await model.ainvoke([{"role": "user", "content": prompt}])
        
        return ResearchResponse(
            success=True,
            report=response.content
        )
        
    except Exception as e:
        import traceback
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return ResearchResponse(
            success=False,
            error=error_details
        )

@app.get("/config")
async def get_config():
    """Get current configuration."""
    try:
        config = Configuration()
        return config.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)