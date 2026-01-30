"""Chainlit UI for Heroku Deep Research.

Features:
- Chat Profiles: Different research modes (Quick, Deep, Expert)
- Starters: Quick research query examples on welcome screen
- Chat Settings: Configure research depth and iterations
- Action Buttons: Copy report, start new research
- Animated progress indicator with step visualization
- Tool call visualization via LangchainCallbackHandler
- Document Elements for research reports
"""

import asyncio
import logging
from datetime import datetime

import chainlit as cl
from chainlit.input_widget import Select, Slider, Switch
from langchain_core.runnables import RunnableConfig

from open_deep_research.deep_researcher import deep_researcher
from open_deep_research.configuration import Configuration, SearchAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Loading animation frames and phases
LOADING_FRAMES = ["◐", "◓", "◑", "◒"]
RESEARCH_PHASES = [
    ("Planning", "Analyzing your question and planning research strategy..."),
    ("Searching", "Searching across multiple sources for relevant information..."),
    ("Reading", "Reading and extracting key insights from sources..."),
    ("Analyzing", "Cross-referencing findings and identifying patterns..."),
    ("Synthesizing", "Combining insights into a comprehensive analysis..."),
    ("Writing", "Composing your research report with citations..."),
]

# Research mode configurations
RESEARCH_MODES = {
    "quick": {
        "name": "Quick Research",
        "icon": "/public/quantum.svg",
        "description": "Fast answers with essential sources. Best for simple questions.",
        "max_iterations": 1,
        "max_concurrent": 2,
    },
    "standard": {
        "name": "Standard Research",
        "icon": "/public/market.svg",
        "description": "Balanced depth and speed. Good for most research needs.",
        "max_iterations": 2,
        "max_concurrent": 3,
    },
    "deep": {
        "name": "Deep Research",
        "icon": "/public/healthcare.svg",
        "description": "Thorough analysis with multiple iterations. For complex topics.",
        "max_iterations": 3,
        "max_concurrent": 4,
    },
    "expert": {
        "name": "Expert Research",
        "icon": "/public/climate.svg",
        "description": "Maximum depth and rigor. For academic or professional research.",
        "max_iterations": 5,
        "max_concurrent": 5,
    },
}


# ============================================
# CHAT PROFILES - Different research modes
# ============================================
@cl.set_chat_profiles
async def chat_profiles():
    """Define chat profiles for different research modes."""
    return [
        cl.ChatProfile(
            name="Quick Research",
            markdown_description="**Fast answers** with essential sources.\nBest for simple questions and quick lookups.",
            icon="/public/quantum.svg",
            default=False,
        ),
        cl.ChatProfile(
            name="Standard Research",
            markdown_description="**Balanced depth** and speed.\nGood for most research needs.",
            icon="/public/market.svg",
            default=True,
        ),
        cl.ChatProfile(
            name="Deep Research",
            markdown_description="**Thorough analysis** with multiple iterations.\nFor complex topics requiring depth.",
            icon="/public/healthcare.svg",
            default=False,
        ),
        cl.ChatProfile(
            name="Expert Research",
            markdown_description="**Maximum rigor** with comprehensive coverage.\nFor academic or professional research.",
            icon="/public/climate.svg",
            default=False,
        ),
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
            message="What are the latest breakthroughs in AI-powered medical diagnosis and treatment? Include recent clinical trials, FDA approvals, and leading companies in this space.",
            icon="/public/healthcare.svg",
        ),
        cl.Starter(
            label="Climate Technology",
            message="Research the most promising climate technology solutions for carbon capture and removal. What companies are leading, what's the current deployment status, and what are the costs per ton of CO2?",
            icon="/public/climate.svg",
        ),
        cl.Starter(
            label="Quantum Computing",
            message="What is the current state of quantum computing? Compare the approaches of IBM, Google, IonQ, and leading startups. What are the near-term practical applications?",
            icon="/public/quantum.svg",
        ),
        cl.Starter(
            label="Market Analysis",
            message="Analyze the current state of the electric vehicle market globally. Who are the major players, what are the key trends, market share data, and outlook for the next 3 years?",
            icon="/public/market.svg",
        ),
    ]


# ============================================
# CHAT SETTINGS - User-configurable options
# ============================================
def get_profile_config(profile_name: str) -> dict:
    """Get configuration for a chat profile."""
    profile_map = {
        "Quick Research": RESEARCH_MODES["quick"],
        "Standard Research": RESEARCH_MODES["standard"],
        "Deep Research": RESEARCH_MODES["deep"],
        "Expert Research": RESEARCH_MODES["expert"],
    }
    return profile_map.get(profile_name, RESEARCH_MODES["standard"])


@cl.on_chat_start
async def start():
    """Initialize session with configuration and settings panel."""
    # Get selected chat profile
    chat_profile = cl.user_session.get("chat_profile")
    profile_config = get_profile_config(chat_profile)

    # Initialize configuration with profile defaults
    config = Configuration.from_runnable_config({})
    config.max_researcher_iterations = profile_config["max_iterations"]
    config.max_concurrent_research_units = profile_config["max_concurrent"]
    cl.user_session.set("config", config)

    # Create settings panel with profile-appropriate defaults
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
                initial=profile_config["max_iterations"],
                min=1,
                max=5,
                step=1,
                description="Number of research iterations (higher = more thorough)",
            ),
            Slider(
                id="max_concurrent",
                label="Parallel Researchers",
                initial=profile_config["max_concurrent"],
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

    # Apply settings
    await apply_settings(settings)

    # Log session start
    logger.info(
        f"Session started: profile={chat_profile}, "
        f"iterations={profile_config['max_iterations']}, "
        f"concurrent={profile_config['max_concurrent']}"
    )


async def apply_settings(settings: dict) -> None:
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


# Depth labels mapped to iteration counts
DEPTH_LABELS = {1: "Quick", 2: "Light", 3: "Standard", 4: "Deep", 5: "Expert"}


@cl.on_settings_update
async def settings_update(settings: dict) -> None:
    """Handle settings updates from the UI."""
    await apply_settings(settings)
    depth = int(settings.get("max_iterations", 3))
    depth_label = DEPTH_LABELS.get(depth, "Custom")
    await cl.Message(
        content=f"Settings updated: **{depth_label}** research mode ({depth} iterations)",
        author="System",
    ).send()


# ============================================
# ACTION BUTTON HANDLERS
# ============================================
@cl.action_callback("copy_report")
async def on_copy_report(action: cl.Action):
    """Handle copy report action."""
    await cl.Message(
        content="Report copied to clipboard! You can paste it anywhere.",
        author="System",
    ).send()
    await action.remove()


@cl.action_callback("new_research")
async def on_new_research(action: cl.Action):
    """Handle new research action."""
    await cl.Message(
        content="Ready for your next research question! Type your query below or choose a starter topic.",
        author="System",
    ).send()
    await action.remove()


@cl.action_callback("save_report")
async def on_save_report(action: cl.Action):
    """Handle save report action."""
    report_content = action.payload.get("report", "")
    if report_content:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"research_report_{timestamp}.md"

        # Create a file element for download
        file_element = cl.File(
            name=filename,
            content=report_content.encode("utf-8"),
            display="inline",
            mime="text/markdown",
        )

        await cl.Message(
            content=f"Your report is ready for download:",
            elements=[file_element],
            author="System",
        ).send()
    await action.remove()


# ============================================
# ANIMATED LOADING INDICATOR
# ============================================
async def animate_loading(status_msg: cl.Message, stop_event: asyncio.Event):
    """Animate loading indicator while research runs."""
    frame_idx = 0
    phase_idx = 0
    dots = 0

    while not stop_event.is_set():
        frame = LOADING_FRAMES[frame_idx % len(LOADING_FRAMES)]
        phase_name, phase_desc = RESEARCH_PHASES[phase_idx % len(RESEARCH_PHASES)]
        dot_str = "." * (dots % 4)

        status_msg.content = f"{frame} **{phase_name}**{dot_str}\n\n_{phase_desc}_"
        await status_msg.update()

        frame_idx += 1
        dots += 1
        if frame_idx % 12 == 0:  # Change phase every 12 frames (~6 seconds)
            phase_idx += 1

        await asyncio.sleep(0.5)


# ============================================
# MESSAGE HANDLER - Research execution
# ============================================
@cl.on_message
async def main(message: cl.Message):
    """Handle research requests with animated progress feedback."""
    config = cl.user_session.get("config")

    # Ensure config exists (may be None if session wasn't initialized)
    if config is None:
        config = Configuration.from_runnable_config({})
        cl.user_session.set("config", config)

    # Get chat profile for context
    chat_profile = cl.user_session.get("chat_profile") or "Standard Research"

    # Create status message with loading animation
    status_msg = cl.Message(
        content="**Starting research...**\n\n_Preparing to analyze your question..._",
        author="Deep Research",
    )
    await status_msg.send()

    # Start loading animation in background
    stop_animation = asyncio.Event()
    animation_task = asyncio.create_task(animate_loading(status_msg, stop_animation))

    try:
        # Run research with step visualization
        async with cl.Step(name="Research Pipeline", type="run") as research_step:
            research_step.input = message.content

            result = await deep_researcher.ainvoke(
                {"messages": [{"role": "user", "content": message.content}]},
                config=RunnableConfig(
                    callbacks=[cl.LangchainCallbackHandler()],
                    configurable=config.model_dump()
                )
            )

            research_step.output = "Research completed successfully"

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
            # Create action buttons for the report
            actions = [
                cl.Action(
                    name="copy_report",
                    label="Copy Report",
                    icon="clipboard",
                    payload={"report": report},
                    collapsed=False,
                ),
                cl.Action(
                    name="save_report",
                    label="Save as File",
                    icon="download",
                    payload={"report": report},
                    collapsed=False,
                ),
                cl.Action(
                    name="new_research",
                    label="New Research",
                    icon="refresh",
                    payload={},
                    collapsed=False,
                ),
            ]

            # Create document element for full report (opens in side panel)
            report_element = cl.Text(
                name="Full Research Report",
                content=report,
                display="side",
            )

            # Send the report with elements and actions
            await cl.Message(
                content=report,
                elements=[report_element],
                actions=actions,
                author="Deep Research",
            ).send()

            logger.info(f"Research completed: profile={chat_profile}, query_len={len(message.content)}")
        else:
            await cl.Message(
                content="**Research completed** but no report was generated.\n\nPlease try again with a different or more specific query.",
                author="System",
            ).send()
            logger.warning("Research completed but no report generated")

    except Exception as e:
        # Stop animation on error
        stop_animation.set()
        await animation_task

        # Remove status message
        await status_msg.remove()

        logger.error(f"Research failed: {e}")

        # Create helpful error message with retry action
        error_actions = [
            cl.Action(
                name="new_research",
                label="Try Again",
                icon="refresh",
                payload={},
                collapsed=False,
            ),
        ]

        await cl.Message(
            content=f"**Research encountered an error**\n\n{str(e)}\n\n_Try rephrasing your query or adjusting the research settings._",
            actions=error_actions,
            author="System",
        ).send()
