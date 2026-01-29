"""Chainlit UI for Open Deep Research with full UI affordances.

Features:
- Tool call visualization via LangchainCallbackHandler
- Research progress Steps
- Document Elements for reports
"""

import logging

import chainlit as cl
from langchain_core.runnables import RunnableConfig

from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
@cl.on_chat_start
async def start():
    """Initialize session with configuration."""
    config = Configuration.from_runnable_config({})
    cl.user_session.set("config", config)
    logger.info(f"Session started: model={config.research_model}, search={config.search_api}")


@cl.on_message
async def main(message: cl.Message):
    """Handle research requests with full UI visualization."""
    config = cl.user_session.get("config")

    # LangChain callback handler for automatic tool step visualization
    cb = cl.LangchainCallbackHandler()

    # Parent step wraps entire research process
    async with cl.Step(name="Deep Research", type="run") as parent_step:
        parent_step.input = message.content

        try:
            # Run research with callback handler for tool visualization
            result = await deep_researcher.ainvoke(
                {"messages": [{"role": "user", "content": message.content}]},
                config=RunnableConfig(
                    callbacks=[cb],
                    configurable=config.model_dump()
                )
            )

            # Extract report from result messages
            report = None
            if result and "messages" in result:
                for m in reversed(result["messages"]):
                    if hasattr(m, "content") and m.content:
                        report = m.content
                        break

            if report:
                parent_step.output = "Research completed"

                # Create document element for full report (clickable in sidebar)
                report_element = cl.Text(
                    name="Full Research Report",
                    content=report,
                    display="side"
                )

                # Send the full report with element attachment
                await cl.Message(
                    content=report,
                    elements=[report_element]
                ).send()

                logger.info("Research completed successfully")
            else:
                parent_step.output = "No report generated"
                await cl.Message(
                    content="Research completed but no report was generated. Please try again."
                ).send()
                logger.warning("Research completed but no report generated")

        except Exception as e:
            logger.error(f"Research failed: {e}")
            parent_step.output = f"Error: {e}"
            await cl.Message(
                content=f"Research failed: {e}\n\nPlease try again or rephrase your query."
            ).send()


@cl.on_settings_update
async def settings_update(settings):
    """Handle settings updates from the UI."""
    logger.info(f"Settings updated: {settings}")
