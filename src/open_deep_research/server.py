"""FastAPI API server for Deep Research agent.

This provides a REST API for programmatic access to the research agent.
For the web UI, use the Chainlit app (chainlit_app.py).
"""

import asyncio
import logging
import os
import time
import traceback
import uuid
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Open Deep Research API",
    description="REST API for deep research agent. For web UI, use the Chainlit interface.",
    version="0.0.17"
)

# Add CORS middleware with configurable origins
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
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

def run_research_background_sync(job_id: str, query: str, config_dict: Dict):
    """Synchronous wrapper to run async research in background."""
    logger.info(f"Starting background research for job {job_id}")

    # Create new event loop for this background task
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(run_research_background_async(job_id, query, config_dict))
        logger.info(f"Research completed for job {job_id}")
        return result
    except Exception as e:
        logger.error(f"Exception in background research for job {job_id}: {str(e)}")
        if job_id in jobs_storage:
            jobs_storage[job_id]["status"] = "failed"
            jobs_storage[job_id]["error"] = str(e)
            jobs_storage[job_id]["progress"] = f"Background task failed: {str(e)}"
            jobs_storage[job_id]["updated_at"] = time.time()
    finally:
        loop.close()

async def run_research_background_async(job_id: str, query: str, config_dict: Dict):
    """Run research in background and update job status."""
    try:
        if job_id not in jobs_storage:
            logger.error(f"Job {job_id} not found in storage")
            return

        # Update job status to in_progress
        jobs_storage[job_id]["status"] = "in_progress"
        jobs_storage[job_id]["progress"] = "Starting research analysis..."
        jobs_storage[job_id]["updated_at"] = time.time()

        # Create configuration and run research
        configuration = Configuration(**config_dict)
        jobs_storage[job_id]["progress"] = "Research workflow started..."
        jobs_storage[job_id]["updated_at"] = time.time()

        result = await deep_researcher.ainvoke(
            {"messages": [{"role": "user", "content": query}]},
            config={"configurable": configuration.model_dump()}
        )

        # Extract the final research report
        report = None
        if result and "messages" in result:
            for message in reversed(result["messages"]):
                if hasattr(message, "content") and message.content:
                    report = message.content
                    break

        # Update job as completed
        jobs_storage[job_id]["status"] = "completed"
        jobs_storage[job_id]["result"] = report or "Research completed but no report was generated."
        jobs_storage[job_id]["progress"] = "Research completed successfully"
        jobs_storage[job_id]["updated_at"] = time.time()
        logger.info(f"Job {job_id} completed successfully")

    except Exception as e:
        error_trace = traceback.format_exc()
        logger.error(f"Exception in background research for job {job_id}: {str(e)}")

        if job_id in jobs_storage:
            jobs_storage[job_id]["status"] = "failed"
            jobs_storage[job_id]["error"] = f"{str(e)}\n\nTraceback:\n{error_trace}"
            jobs_storage[job_id]["progress"] = f"Research failed: {str(e)}"
            jobs_storage[job_id]["updated_at"] = time.time()

@app.get("/")
async def root():
    """Redirect to API documentation."""
    return RedirectResponse(url="/docs")

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/research", response_model=ResearchResponse)
async def conduct_research(request: ResearchRequest):
    """Conduct deep research and generate a report (synchronous endpoint)."""
    try:
        config_dict = request.config or {}

        # Use Heroku Inference API if available
        if os.getenv("INFERENCE_KEY"):
            heroku_model = os.getenv("HEROKU_MODEL", "openai:claude-4-sonnet")
            config_dict.update({
                "research_model": heroku_model,
                "summarization_model": heroku_model,
                "compression_model": heroku_model,
                "final_report_model": heroku_model,
                "search_api": "brightdata",
                "allow_clarification": False
            })

        if not (os.getenv("INFERENCE_KEY") or os.getenv("OPENAI_API_KEY")):
            return ResearchResponse(
                success=False,
                error="No API key configured. Please set INFERENCE_KEY or OPENAI_API_KEY."
            )

        configuration = Configuration(**config_dict)
        result = await deep_researcher.ainvoke(
            {"messages": [{"role": "user", "content": request.query}]},
            config={"configurable": configuration.model_dump()}
        )

        # Extract the final research report
        report = None
        if result and "messages" in result:
            for message in reversed(result["messages"]):
                if hasattr(message, "content") and message.content:
                    report = message.content
                    break

        return ResearchResponse(
            success=True,
            report=report or "Research completed but no report was generated."
        )

    except Exception as e:
        error_details = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        return ResearchResponse(success=False, error=error_details)

@app.post("/research/async", response_model=ResearchJobResponse)
async def start_research_async(request: ResearchRequest, background_tasks: BackgroundTasks):
    """Start research in background and return job ID for polling."""
    try:
        job_id = str(uuid.uuid4())
        config_dict = request.config or {}

        # Use Heroku Inference API if available
        if os.getenv("INFERENCE_KEY"):
            heroku_model = os.getenv("HEROKU_MODEL", "openai:claude-4-sonnet")
            config_dict.update({
                "research_model": heroku_model,
                "summarization_model": heroku_model,
                "compression_model": heroku_model,
                "final_report_model": heroku_model,
            })

        if not (os.getenv("INFERENCE_KEY") or os.getenv("OPENAI_API_KEY")):
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

        background_tasks.add_task(run_research_background_sync, job_id, request.query, config_dict)

        return ResearchJobResponse(
            job_id=job_id,
            status="pending",
            message="Research job started. Use job_id to poll for status."
        )

    except Exception as e:
        logger.error(f"Failed to start research job: {str(e)}")
        return ResearchJobResponse(job_id="", status="failed", message=str(e))

@app.get("/research/status/{job_id}", response_model=JobStatusResponse)
async def get_research_status(job_id: str):
    """Get status of research job."""
    if job_id not in jobs_storage:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(**jobs_storage[job_id])

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