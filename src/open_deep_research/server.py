"""FastAPI server for deploying Deep Research agent to Heroku."""

import os
import uuid
import time
import asyncio
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
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

class ResearchJobResponse(BaseModel):
    """Response model for async research job initiation."""
    job_id: str
    status: str
    message: str

class JobStatusResponse(BaseModel):
    """Response model for job status polling."""
    job_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    progress: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: float
    updated_at: float

# In-memory job storage (in production, use Redis or database)
jobs_storage = {}

async def run_research_background(job_id: str, query: str, config_dict: Dict):
    """Run research in background and update job status."""
    import traceback
    
    try:
        print(f"DEBUG: Starting background research for job {job_id} with query: {query}")
        
        # Update job status to in_progress
        jobs_storage[job_id]["status"] = "in_progress"
        jobs_storage[job_id]["progress"] = "Starting research analysis..."
        jobs_storage[job_id]["updated_at"] = time.time()
        
        print(f"DEBUG: Creating configuration with config_dict: {config_dict}")
        
        # Create configuration
        configuration = Configuration(**config_dict)
        
        print(f"DEBUG: Configuration created successfully: {configuration.model_dump()}")
        
        # Update progress
        jobs_storage[job_id]["progress"] = "Initializing research workflow..."
        jobs_storage[job_id]["updated_at"] = time.time()
        
        print(f"DEBUG: About to invoke deep_researcher.ainvoke")
        
        # Run the research
        result = await deep_researcher.ainvoke(
            {"messages": [{"role": "user", "content": query}]},
            config={"configurable": configuration.model_dump()}
        )
        
        print(f"DEBUG: Deep researcher completed. Result type: {type(result)}")
        print(f"DEBUG: Result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
        
        # Update progress after research completion
        jobs_storage[job_id]["progress"] = "Processing research results..."
        jobs_storage[job_id]["updated_at"] = time.time()
        
        # Extract the final research report
        report = None
        if result and "messages" in result:
            print(f"DEBUG: Found {len(result['messages'])} messages in result")
            for i, message in enumerate(reversed(result["messages"])):
                print(f"DEBUG: Message {i}: type={type(message)}, has_content={hasattr(message, 'content')}")
                if hasattr(message, "content"):
                    print(f"DEBUG: Message {i} content length: {len(str(message.content)) if message.content else 0}")
                    if message.content:
                        report = message.content
                        print(f"DEBUG: Using message {i} as final report")
                        break
        else:
            print(f"DEBUG: No messages found in result or result is None")
        
        print(f"DEBUG: Final report length: {len(str(report)) if report else 0}")
        
        # Update job as completed
        jobs_storage[job_id]["status"] = "completed"
        jobs_storage[job_id]["result"] = report or "Research completed but no report was generated."
        jobs_storage[job_id]["progress"] = "Research completed successfully"
        jobs_storage[job_id]["updated_at"] = time.time()
        
        print(f"DEBUG: Job {job_id} completed successfully")
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"ERROR: Exception in background research for job {job_id}: {str(e)}")
        print(f"ERROR: Full traceback:\n{error_trace}")
        
        # Update job as failed
        jobs_storage[job_id]["status"] = "failed"
        jobs_storage[job_id]["error"] = f"{str(e)}\n\nTraceback:\n{error_trace}"
        jobs_storage[job_id]["progress"] = f"Research failed: {str(e)}"
        jobs_storage[job_id]["updated_at"] = time.time()

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
                "final_report_model": "openai:claude-4-sonnet",
                "search_api": "brightdata",  # Use Bright Data for web search
                "allow_clarification": False  # Disable clarification to avoid empty message issues
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
        
        # Use the full LangGraph deep research workflow
        configuration = Configuration(**config_dict)
        
        # Run the actual deep research agent
        result = await deep_researcher.ainvoke(
            {"messages": [{"role": "user", "content": request.query}]},
            config={"configurable": configuration.model_dump()}
        )
        
        # Extract the final research report
        report = None
        if result and "messages" in result:
            # Get the last message which should be the final report
            for message in reversed(result["messages"]):
                if hasattr(message, "content") and message.content:
                    report = message.content
                    break
        
        return ResearchResponse(
            success=True,
            report=report or "Research completed but no report was generated."
        )
        
    except Exception as e:
        import traceback
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return ResearchResponse(
            success=False,
            error=error_details
        )

@app.post("/research/async", response_model=ResearchJobResponse)
async def start_research_async(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Start research in background and return job ID for polling."""
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create configuration with Heroku-specific settings
        config_dict = request.config or {}
        
        # Use Heroku Inference API if available
        if os.getenv("INFERENCE_KEY"):
            config_dict.update({
                "research_model": "openai:claude-4-sonnet",
                "summarization_model": "openai:claude-4-sonnet", 
                "compression_model": "openai:claude-4-sonnet",
                "final_report_model": "openai:claude-4-sonnet",
                "api_key": os.getenv("INFERENCE_KEY"),
                "base_url": "https://claude-4-sonnet-q82vgkr8.apps.inference.ai/v1"
            })
        
        # Get API key and base URL for Heroku Inference
        api_key = os.getenv("INFERENCE_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        
        if not api_key:
            return ResearchJobResponse(
                job_id="",
                status="failed",
                message="No API key configured. Please set INFERENCE_KEY or OPENAI_API_KEY."
            )
        
        # Initialize job in storage
        current_time = time.time()
        jobs_storage[job_id] = {
            "job_id": job_id,
            "status": "pending",
            "progress": "Job queued for processing",
            "result": None,
            "error": None,
            "created_at": current_time,
            "updated_at": current_time,
            "query": request.query
        }
        
        # Start background task
        background_tasks.add_task(run_research_background, job_id, request.query, config_dict)
        
        return ResearchJobResponse(
            job_id=job_id,
            status="pending",
            message="Research job started. Use job_id to poll for status."
        )
        
    except Exception as e:
        return ResearchJobResponse(
            job_id="",
            status="failed",
            message=str(e)
        )

@app.get("/research/status/{job_id}", response_model=JobStatusResponse)
async def get_research_status(job_id: str):
    """Get status of research job."""
    if job_id not in jobs_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs_storage[job_id]
    return JobStatusResponse(**job_data)

@app.get("/config")
async def get_config():
    """Get current configuration."""
    try:
        config = Configuration()
        return config.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def test_background_task(job_id: str):
    """Simple test background task."""
    print(f"DEBUG: Test background task started for job {job_id}")
    import asyncio
    await asyncio.sleep(2)
    print(f"DEBUG: Test background task completing for job {job_id}")
    jobs_storage[job_id]["status"] = "completed"
    jobs_storage[job_id]["result"] = "Test task completed successfully!"
    jobs_storage[job_id]["progress"] = "Test completed"
    jobs_storage[job_id]["updated_at"] = time.time()
    print(f"DEBUG: Test background task finished for job {job_id}")

@app.post("/test/async")
async def test_async_task(background_tasks: BackgroundTasks):
    """Test background task execution."""
    job_id = str(uuid.uuid4())
    
    # Initialize job in storage
    current_time = time.time()
    jobs_storage[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": "Test task queued",
        "result": None,
        "error": None,
        "created_at": current_time,
        "updated_at": current_time,
        "query": "test"
    }
    
    print(f"DEBUG: Starting test background task for job {job_id}")
    background_tasks.add_task(test_background_task, job_id)
    
    return {"job_id": job_id, "status": "pending", "message": "Test task started"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)