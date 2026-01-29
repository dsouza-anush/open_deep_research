"""Chainlit UI for Heroku Deep Research.

Features:
- Starters: Quick research query examples on welcome screen
- Chat Settings: Configure research depth and iterations
- Animated progress indicator during research
- Tool call visualization via LangchainCallbackHandler
- Document Elements for research reports
"""

import asyncio
import logging

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch
from langchain_core.runnables import RunnableConfig

from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration, SearchAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Loading animation frames
LOADING_FRAMES = ["◐", "◓", "◑", "◒"]
RESEARCH_PHASES = [
    "Planning research strategy",
    "Searching for sources",
    "Analyzing documents",
    "Synthesizing findings",
    "Writing report",
]


# ============================================
# STARTERS - Quick research query examples
# ============================================
@cl.set_starters
async def set_starters():
    """Define starter prompts for the welcome screen."""
    return [
        cl.Starter(
            label="AI in Healthcare",
            message="What are the latest breakthroughs in AI-powered medical diagnosis and treatment? Include recent clinical trials and FDA approvals.",
            icon="/public/healthcare.svg",
        ),
        cl.Starter(
            label="Climate Tech",
            message="Research the most promising climate technology solutions for carbon capture. What companies are leading and what's the current state of deployment?",
            icon="/public/climate.svg",
        ),
        cl.Starter(
            label="Quantum Computing",
            message="What is the current state of quantum computing in 2025? Compare IBM, Google, and startup approaches to achieving quantum advantage.",
            icon="/public/quantum.svg",
        ),
        cl.Starter(
            label="Market Analysis",
            message="Analyze the current state of the electric vehicle market. Who are the major players, what are the trends, and what's the outlook for 2026?",
            icon="/public/market.svg",
        ),
    ]


# ============================================
# CHAT SETTINGS - User-configurable options
# ============================================
@cl.on_chat_start
async def start():
    """Initialize session with configuration and settings panel."""
    config = Configuration.from_runnable_config({})
    cl.user_session.set("config", config)

    # Create settings panel
    settings = await cl.ChatSettings(
        [
            Select(
                id="search_api",
                label="Search Provider",
                values=["tavily", "none"],
                initial_index=0 if config.search_api == SearchAPI.TAVILY else 1,
                description="Web search API for gathering research data",
            ),
            Slider(
                id="max_iterations",
                label="Research Depth",
                initial=config.max_researcher_iterations,
                min=1,
                max=5,
                step=1,
                description="Number of research iterations (higher = more thorough)",
            ),
            Slider(
                id="max_concurrent",
                label="Parallel Researchers",
                initial=config.max_concurrent_research_units,
                min=1,
                max=5,
                step=1,
                description="Number of parallel research agents",
            ),
            Switch(
                id="allow_clarification",
                label="Ask Clarifying Questions",
                initial=config.allow_clarification,
                description="Allow the researcher to ask questions before starting",
            ),
        ]
    ).send()

    # Apply any immediate settings
    await apply_settings(settings)

    logger.info(f"Session started: model={config.research_model}, search={config.search_api}")


async def apply_settings(settings: dict):
    """Apply settings to the current configuration."""
    config = cl.user_session.get("config")
    if not config:
        return

    # Update configuration based on settings
    if "search_api" in settings:
        config.search_api = SearchAPI(settings["search_api"])
    if "max_iterations" in settings:
        config.max_researcher_iterations = int(settings["max_iterations"])
    if "max_concurrent" in settings:
        config.max_concurrent_research_units = int(settings["max_concurrent"])
    if "allow_clarification" in settings:
        config.allow_clarification = settings["allow_clarification"]

    cl.user_session.set("config", config)
    logger.info(f"Settings applied: {settings}")


@cl.on_settings_update
async def settings_update(settings: dict):
    """Handle settings updates from the UI."""
    await apply_settings(settings)
    await cl.Message(
        content=f"⚙️ Settings updated! Research depth: {settings.get('max_iterations', 3)} iterations"
    ).send()


# ============================================
# ANIMATED LOADING INDICATOR
# ============================================
async def animate_loading(status_msg: cl.Message, stop_event: asyncio.Event):
    """Animate loading indicator while research runs."""
    frame_idx = 0
    phase_idx = 0

    while not stop_event.is_set():
        frame = LOADING_FRAMES[frame_idx % len(LOADING_FRAMES)]
        phase = RESEARCH_PHASES[phase_idx % len(RESEARCH_PHASES)]

        status_msg.content = f"{frame} **{phase}...**"
        await status_msg.update()

        frame_idx += 1
        if frame_idx % 8 == 0:  # Change phase every 8 frames (~4 seconds)
            phase_idx += 1

        await asyncio.sleep(0.5)


# ============================================
# MESSAGE HANDLER - Research execution
# ============================================
@cl.on_message
async def main(message: cl.Message):
    """Handle research requests with animated progress feedback."""
    config = cl.user_session.get("config")

    # Create status message with loading animation
    status_msg = cl.Message(content="◐ **Starting research...**")
    await status_msg.send()

    # Start loading animation in background
    stop_animation = asyncio.Event()
    animation_task = asyncio.create_task(animate_loading(status_msg, stop_animation))

    # LangChain callback handler auto-creates steps for all LangGraph operations
    cb = cl.LangchainCallbackHandler()

    try:
        # Run research with step visualization
        async with cl.Step(name="Deep Research", type="run") as research_step:
            research_step.input = message.content

            result = await deep_researcher.ainvoke(
                {"messages": [{"role": "user", "content": message.content}]},
                config=RunnableConfig(
                    callbacks=[cb],
                    configurable=config.model_dump()
                )
            )

            research_step.output = "Research completed"

        # Stop animation
        stop_animation.set()
        await animation_task

        # Remove status message
        await status_msg.remove()

        # Extract report from result messages
        report = None
        if result and "messages" in result:
            for m in reversed(result["messages"]):
                if hasattr(m, "content") and m.content:
                    report = m.content
                    break

        if report:
            # Create document element for full report (opens in side panel)
            report_element = cl.Text(
                name="📄 Full Research Report",
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
                content="⚠️ Research completed but no report was generated. Please try again with a different query."
            ).send()
            logger.warning("Research completed but no report generated")

    except Exception as e:
        # Stop animation on error
        stop_animation.set()
        await animation_task

        # Remove status message
        await status_msg.remove()

        logger.error(f"Research failed: {e}")
        await cl.Message(
            content=f"❌ **Research failed:** {e}\n\nPlease try again or rephrase your query."
        ).send()
