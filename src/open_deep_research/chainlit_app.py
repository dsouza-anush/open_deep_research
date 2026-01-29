"""Chainlit UI for Open Deep Research.

This provides a premium chat interface for the deep research agent,
with streaming support and beautiful markdown rendering.
"""

import logging
import os

import chainlit as cl

from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@cl.on_chat_start
async def start():
    """Initialize session with configuration."""
    config = Configuration()
    cl.user_session.set("config", config)

    # Welcome message
    await cl.Message(
        content="# Welcome to Open Deep Research\n\n"
        "I can conduct comprehensive research on any topic you're interested in. "
        "Just ask me a question and I'll search the web, analyze sources, and provide "
        "a detailed research report.\n\n"
        "**Example queries:**\n"
        "- What are the latest advancements in quantum computing?\n"
        "- How does mRNA vaccine technology work?\n"
        "- What is the current state of renewable energy adoption?\n\n"
        "*Powered by Claude 4 Sonnet and Bright Data*"
    ).send()


@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages and run research."""
    config = cl.user_session.get("config")

    # Create a message to stream updates
    msg = cl.Message(content="")
    await msg.send()

    # Update with initial status
    msg.content = "🔍 **Starting research...**\n\nAnalyzing your query and planning research strategy..."
    await msg.update()

    try:
        # Run the deep research workflow
        logger.info(f"Starting research for query: {message.content[:100]}...")

        result = await deep_researcher.ainvoke(
            {"messages": [{"role": "user", "content": message.content}]},
            config={"configurable": config.model_dump()}
        )

        # Extract the final report
        report = None
        if result and "messages" in result:
            for m in reversed(result["messages"]):
                if hasattr(m, "content") and m.content:
                    report = m.content
                    break

        if report:
            msg.content = report
            logger.info("Research completed successfully")
        else:
            msg.content = "⚠️ Research completed but no report was generated. Please try again."
            logger.warning("Research completed but no report generated")

        await msg.update()

    except Exception as e:
        logger.error(f"Research failed: {str(e)}")
        msg.content = f"❌ **Error during research**\n\n```\n{str(e)}\n```\n\nPlease try again or rephrase your query."
        await msg.update()


@cl.on_settings_update
async def settings_update(settings):
    """Handle settings updates from the UI."""
    logger.info(f"Settings updated: {settings}")


# Optional: Add step visualization for research progress
@cl.step(type="tool")
async def research_step(name: str, description: str):
    """Visualize a research step in the UI."""
    return f"Completed: {name}"
