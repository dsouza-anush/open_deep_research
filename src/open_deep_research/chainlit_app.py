"""Chainlit UI for Open Deep Research with full UI affordances.

Features:
- Auto-login for demo (enables sidebar/chat history without login form)
- Tool call visualization via LangchainCallbackHandler
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


# ============================================
# AUTHENTICATION (enables sidebar/chat history)
# ============================================
@cl.password_auth_callback
def password_auth_callback(username: str, password: str) -> cl.User | None:
    """Accept any credentials for demo access.

    Enter any username/password (e.g., demo/demo) to access.
    This enables sidebar and chat history features.
    """
    if username:  # Accept any non-empty username
        return cl.User(
            identifier=username,
            metadata={"role": "demo", "provider": "credentials"}
        )
    return None
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

    # LangChain callback handler auto-creates steps for all LangGraph operations
    cb = cl.LangchainCallbackHandler()

    try:
        # Run research - callback handler shows all tool steps automatically
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
            # Create document element for full report
            report_element = cl.Text(
                name="Full Research Report",
                content=report,
                display="side"
            )

            # Send the report with element attachment
            await cl.Message(
                content=report,
                elements=[report_element]
            ).send()

            logger.info("Research completed successfully")
        else:
            await cl.Message(
                content="Research completed but no report was generated. Please try again."
            ).send()
            logger.warning("Research completed but no report generated")

    except Exception as e:
        logger.error(f"Research failed: {e}")
        await cl.Message(
            content=f"Research failed: {e}\n\nPlease try again or rephrase your query."
        ).send()


@cl.on_settings_update
async def settings_update(settings):
    """Handle settings updates from the UI."""
    logger.info(f"Settings updated: {settings}")
