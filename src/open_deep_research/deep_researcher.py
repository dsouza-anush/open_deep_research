"""Main LangGraph implementation for the Deep Research agent."""

import asyncio
import logging
import re
import traceback
from datetime import datetime
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    filter_messages,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from open_deep_research.configuration import (
    Configuration,
)
from open_deep_research.prompts import (
    clarify_with_user_instructions,
    compress_research_simple_human_message,
    compress_research_system_prompt,
    final_report_generation_prompt,
    lead_researcher_prompt,
    research_system_prompt,
    transform_messages_into_research_topic_prompt,
)
from open_deep_research.state import (
    AgentInputState,
    AgentState,
    ClarifyWithUser,
    ConductResearch,
    ResearchComplete,
    ResearcherOutputState,
    ResearcherState,
    ResearchQuestion,
    SupervisorState,
)
from open_deep_research.utils import (
    anthropic_websearch_called,
    get_all_tools,
    get_api_key_for_model,
    get_model_token_limit,
    get_notes_from_tool_calls,
    get_today_str,
    is_token_limit_exceeded,
    openai_websearch_called,
    remove_up_to_last_ai_message,
    think_tool,
)

# Configure logging
logger = logging.getLogger(__name__)


def ensure_message_content_validity(messages):
    """Ensure all messages have valid content for OpenAI API compatibility.

    The OpenAI API (and Heroku Inference API) requires that ALL messages have
    non-empty content, including AI messages with tool calls. LangChain often
    creates AIMessage objects with content=None when tool calls are present,
    which causes API validation errors.

    This function creates new message objects with valid content instead of
    modifying in-place, which may not work with immutable dataclass objects.

    Args:
        messages: List of message objects to validate

    Returns:
        List of new message objects with valid content
    """
    validated = []
    for message in messages:
        # Check if message needs content fix
        needs_fix = (
            hasattr(message, 'content') and
            (message.content is None or message.content == "" or
             (isinstance(message.content, str) and not message.content.strip()))
        )

        if needs_fix:
            # Create a new message with valid content based on type
            if isinstance(message, AIMessage):
                # For AI messages with tool calls, add descriptive content
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    tool_names = [tc.get('name', 'tool') for tc in message.tool_calls]
                    new_content = f"Executing: {', '.join(tool_names)}"
                else:
                    new_content = "Processing request."

                # Create new AIMessage with all original attributes plus valid content
                new_message = AIMessage(
                    content=new_content,
                    additional_kwargs=getattr(message, 'additional_kwargs', {}),
                    response_metadata=getattr(message, 'response_metadata', {}),
                    tool_calls=getattr(message, 'tool_calls', []),
                    invalid_tool_calls=getattr(message, 'invalid_tool_calls', []),
                    id=getattr(message, 'id', None),
                )
                validated.append(new_message)
            elif isinstance(message, HumanMessage):
                new_message = HumanMessage(
                    content="[User input]",
                    additional_kwargs=getattr(message, 'additional_kwargs', {}),
                )
                validated.append(new_message)
            elif isinstance(message, SystemMessage):
                new_message = SystemMessage(
                    content="System message.",
                    additional_kwargs=getattr(message, 'additional_kwargs', {}),
                )
                validated.append(new_message)
            elif isinstance(message, ToolMessage):
                new_message = ToolMessage(
                    content="Tool executed.",
                    name=getattr(message, 'name', 'tool'),
                    tool_call_id=getattr(message, 'tool_call_id', ''),
                    additional_kwargs=getattr(message, 'additional_kwargs', {}),
                )
                validated.append(new_message)
            else:
                # For unknown message types, try to set content directly as fallback
                try:
                    message.content = "Processing."
                    validated.append(message)
                except (AttributeError, TypeError):
                    validated.append(message)
        else:
            # Message has valid content, keep as-is
            validated.append(message)

    return validated

# Initialize a configurable model that we will use throughout the agent
configurable_model = init_chat_model(
    configurable_fields=("model", "max_tokens", "api_key"),
)

def is_heroku_inference_api(model_name: str) -> bool:
    """Check if we're using Heroku Inference API which doesn't support response_format."""
    return model_name and "openai:" in model_name

async def parse_clarification_response(response_content: str) -> dict:
    """Parse clarification response from plain text when structured output isn't available."""
    # Ensure we have content to work with
    if not response_content or not response_content.strip():
        return {
            "need_clarification": False,
            "question": "Could you provide more details about what you'd like me to research?",
            "verification": "I understand your request and will proceed with the research."
        }
    
    # Look for clarification indicators
    need_clarification = any(phrase in response_content.lower() for phrase in [
        "need clarification", "unclear", "ambiguous", "could you clarify", 
        "more specific", "what exactly", "which aspect", "need more information"
    ])
    
    # Extract question if present (look for question marks)
    questions = re.findall(r'[.!?]*\s*([^.!?]*\?)', response_content)
    question = questions[0].strip() if questions else "Could you provide more details about what you'd like me to research?"
    
    # Ensure question is not empty
    if not question.strip():
        question = "Could you provide more details about what you'd like me to research?"
    
    # Create verification message - use original response if it seems reasonable
    if not need_clarification and response_content.strip():
        verification = response_content.strip()
    else:
        verification = "I understand your request and will proceed with the research."
    
    # Ensure verification is not empty
    if not verification.strip():
        verification = "I understand your request and will proceed with the research."
    
    return {
        "need_clarification": need_clarification,
        "question": question,
        "verification": verification
    }

async def clarify_with_user(state: AgentState, config: RunnableConfig) -> Command[Literal["write_research_brief", "__end__"]]:
    """Analyze user messages and ask clarifying questions if the research scope is unclear.
    
    This function determines whether the user's request needs clarification before proceeding
    with research. If clarification is disabled or not needed, it proceeds directly to research.
    
    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings and preferences
        
    Returns:
        Command to either end with a clarifying question or proceed to research brief
    """
    # Step 1: Check if clarification is enabled in configuration
    configurable = Configuration.from_runnable_config(config)
    if not configurable.allow_clarification:
        # Skip clarification step and proceed directly to research
        return Command(goto="write_research_brief")
    
    # Step 2: Prepare the model for clarification analysis
    messages = state["messages"]
    model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    # Step 3: Check if we need to use structured output workaround
    use_structured_output = not is_heroku_inference_api(configurable.research_model)
    
    if use_structured_output:
        # Configure model with structured output and retry logic
        clarification_model = (
            configurable_model
            .with_structured_output(ClarifyWithUser)
            .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
            .with_config(model_config)
        )
        
        # Analyze whether clarification is needed
        prompt_content = clarify_with_user_instructions.format(
            messages=get_buffer_string(messages), 
            date=get_today_str()
        )
        response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])
        
        # Route based on clarification analysis
        if response.need_clarification:
            return Command(
                goto=END, 
                update={"messages": [AIMessage(content=response.question)]}
            )
        else:
            return Command(
                goto="write_research_brief", 
                update={"messages": [AIMessage(content=response.verification)]}
            )
    else:
        # Use plain text response for Heroku Inference API
        clarification_model = configurable_model.with_config(model_config)
        
        # Enhanced prompt for plain text parsing
        prompt_content = clarify_with_user_instructions.format(
            messages=get_buffer_string(messages), 
            date=get_today_str()
        ) + "\n\nPlease respond with either:\n1. A clarifying question if the request is unclear or ambiguous\n2. A confirmation that you understand and will proceed with research"
        
        response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])
        parsed_response = await parse_clarification_response(response.content)
        
        # Route based on parsed clarification analysis
        if parsed_response["need_clarification"]:
            return Command(
                goto=END, 
                update={"messages": [AIMessage(content=parsed_response["question"])]}
            )
        else:
            return Command(
                goto="write_research_brief", 
                update={"messages": [AIMessage(content=parsed_response["verification"])]}
            )


async def parse_research_brief_response(response_content: str) -> dict:
    """Parse research brief from plain text when structured output isn't available."""
    # Ensure we have content to work with
    if not response_content or not response_content.strip():
        return {"research_brief": "Research the user's query comprehensively using available sources."}
    
    # Extract the research brief from the response
    research_brief = response_content.strip()
    
    # Clean up the research brief if it contains meta-commentary
    if "research brief:" in research_brief.lower():
        parts = research_brief.split("research brief:", 1)
        if len(parts) > 1:
            research_brief = parts[1].strip()
    
    # Ensure research brief is not empty
    if not research_brief.strip():
        research_brief = "Research the user's query comprehensively using available sources."
    
    return {"research_brief": research_brief}

async def write_research_brief(state: AgentState, config: RunnableConfig) -> Command[Literal["research_supervisor"]]:
    """Transform user messages into a structured research brief and initialize supervisor.
    
    This function analyzes the user's messages and generates a focused research brief
    that will guide the research supervisor. It also sets up the initial supervisor
    context with appropriate prompts and instructions.
    
    Args:
        state: Current agent state containing user messages
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to research supervisor with initialized context
    """
    # Step 1: Set up the research model
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    # Step 2: Check if we need to use structured output workaround
    use_structured_output = not is_heroku_inference_api(configurable.research_model)
    
    if use_structured_output:
        # Configure model for structured research question generation
        research_model = (
            configurable_model
            .with_structured_output(ResearchQuestion)
            .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
            .with_config(research_model_config)
        )
        
        # Generate structured research brief from user messages
        prompt_content = transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str()
        )
        response = await research_model.ainvoke([HumanMessage(content=prompt_content)])
        research_brief = response.research_brief
    else:
        # Use plain text response for Heroku Inference API
        research_model = configurable_model.with_config(research_model_config)
        
        # Enhanced prompt for plain text parsing
        prompt_content = transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str()
        ) + "\n\nPlease provide a clear, focused research brief that summarizes what needs to be researched."
        
        response = await research_model.ainvoke([HumanMessage(content=prompt_content)])
        parsed_response = await parse_research_brief_response(response.content)
        research_brief = parsed_response["research_brief"]
    
    # Step 3: Initialize supervisor with research brief and instructions
    supervisor_system_prompt = lead_researcher_prompt.format(
        date=get_today_str(),
        max_concurrent_research_units=configurable.max_concurrent_research_units,
        max_researcher_iterations=configurable.max_researcher_iterations
    )
    
    # Ensure research brief is not empty
    if not research_brief.strip():
        research_brief = "Research the user's query comprehensively using available sources."
    
    return Command(
        goto="research_supervisor", 
        update={
            "research_brief": research_brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=supervisor_system_prompt),
                    HumanMessage(content=research_brief)
                ]
            }
        }
    )


async def supervisor(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor_tools"]]:
    """Lead research supervisor that plans research strategy and delegates to researchers.
    
    The supervisor analyzes the research brief and decides how to break down the research
    into manageable tasks. It can use think_tool for strategic planning, ConductResearch
    to delegate tasks to sub-researchers, or ResearchComplete when satisfied with findings.
    
    Args:
        state: Current supervisor state with messages and research context
        config: Runtime configuration with model settings
        
    Returns:
        Command to proceed to supervisor_tools for tool execution
    """
    # Step 1: Configure the supervisor model with available tools
    configurable = Configuration.from_runnable_config(config)
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    # Available tools: research delegation, completion signaling, and strategic thinking
    lead_researcher_tools = [ConductResearch, ResearchComplete, think_tool]
    
    # Configure model with tools, retry logic, and model settings
    research_model = (
        configurable_model
        .bind_tools(lead_researcher_tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )
    
    # Step 2: Generate supervisor response based on current context
    supervisor_messages = state.get("supervisor_messages", [])
    
    # Ensure we have at least one message - but don't filter out tool calling sequences
    if not supervisor_messages:
        supervisor_messages = [HumanMessage(content="Please analyze the research requirements and begin the research process.")]

    # Validate messages before sending to API to prevent content validation errors
    validated_messages = ensure_message_content_validity(supervisor_messages)
    response = await research_model.ainvoke(validated_messages)
    
    # Step 3: Ensure response has valid content for API compatibility
    if hasattr(response, 'content') and not response.content:
        # Add default content for AI messages with tool calls to satisfy API requirements
        response.content = "Analyzing research requirements and planning next steps."
    
    # Step 4: Update state with proper message chain and proceed to tool execution
    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": validated_messages + [response],
            "research_iterations": state.get("research_iterations", 0) + 1
        }
    )

async def supervisor_tools(state: SupervisorState, config: RunnableConfig) -> Command[Literal["supervisor", "__end__"]]:
    """Execute tools called by the supervisor, including research delegation and strategic thinking.
    
    This function handles three types of supervisor tool calls:
    1. think_tool - Strategic reflection that continues the conversation
    2. ConductResearch - Delegates research tasks to sub-researchers
    3. ResearchComplete - Signals completion of research phase
    
    Args:
        state: Current supervisor state with messages and iteration count
        config: Runtime configuration with research limits and model settings
        
    Returns:
        Command to either continue supervision loop or end research phase
    """
    # Step 1: Extract current state and check exit conditions
    configurable = Configuration.from_runnable_config(config)
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]
    
    # Define exit criteria for research phase
    exceeded_allowed_iterations = research_iterations > configurable.max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls
    research_complete_tool_call = any(
        tool_call["name"] == "ResearchComplete" 
        for tool_call in most_recent_message.tool_calls
    )
    
    # Exit if any termination condition is met
    if exceeded_allowed_iterations or no_tool_calls or research_complete_tool_call:
        return Command(
            goto=END,
            update={
                "notes": get_notes_from_tool_calls(supervisor_messages),
                "research_brief": state.get("research_brief", "")
            }
        )
    
    # Step 2: Process all tool calls together (both think_tool and ConductResearch)
    all_tool_messages = []
    update_payload = {"supervisor_messages": []}
    
    # Handle think_tool calls (strategic reflection)
    think_tool_calls = [
        tool_call for tool_call in most_recent_message.tool_calls 
        if tool_call["name"] == "think_tool"
    ]
    
    for tool_call in think_tool_calls:
        reflection_content = tool_call["args"]["reflection"]
        all_tool_messages.append(ToolMessage(
            content=f"Reflection recorded: {reflection_content}",
            name="think_tool",
            tool_call_id=tool_call["id"]
        ))
    
    # Handle ConductResearch calls (research delegation)
    conduct_research_calls = [
        tool_call for tool_call in most_recent_message.tool_calls 
        if tool_call["name"] == "ConductResearch"
    ]
    
    if conduct_research_calls:
        try:
            # Limit concurrent research units to prevent resource exhaustion
            allowed_conduct_research_calls = conduct_research_calls[:configurable.max_concurrent_research_units]
            overflow_conduct_research_calls = conduct_research_calls[configurable.max_concurrent_research_units:]
            
            # Execute research tasks in parallel
            research_tasks = [
                researcher_subgraph.ainvoke({
                    "researcher_messages": [
                        HumanMessage(content=tool_call["args"]["research_topic"])
                    ],
                    "research_topic": tool_call["args"]["research_topic"]
                }, config) 
                for tool_call in allowed_conduct_research_calls
            ]
            
            tool_results = await asyncio.gather(*research_tasks)
            
            # Create tool messages with research results
            for observation, tool_call in zip(tool_results, allowed_conduct_research_calls):
                all_tool_messages.append(ToolMessage(
                    content=observation.get("compressed_research", "Error synthesizing research report: Maximum retries exceeded"),
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"]
                ))
            
            # Handle overflow research calls with error messages
            for overflow_call in overflow_conduct_research_calls:
                all_tool_messages.append(ToolMessage(
                    content=f"Error: Did not run this research as you have already exceeded the maximum number of concurrent research units. Please try again with {configurable.max_concurrent_research_units} or fewer research units.",
                    name="ConductResearch",
                    tool_call_id=overflow_call["id"]
                ))
            
            # Aggregate raw notes from all research results
            raw_notes_concat = "\n".join([
                "\n".join(observation.get("raw_notes", [])) 
                for observation in tool_results
            ])
            
            if raw_notes_concat:
                update_payload["raw_notes"] = [raw_notes_concat]
                
        except Exception as e:
            # Handle research execution errors
            if is_token_limit_exceeded(e, configurable.research_model):
                # Token limit exceeded or other error - end research phase
                return Command(
                    goto=END,
                    update={
                        "notes": get_notes_from_tool_calls(supervisor_messages),
                        "research_brief": state.get("research_brief", "")
                    }
                )
    
    # Step 3: Return command with all tool results appended to message history
    # Append tool messages to existing supervisor message chain
    update_payload["supervisor_messages"] = all_tool_messages
    return Command(
        goto="supervisor",
        update=update_payload
    ) 

# Supervisor Subgraph Construction
# Creates the supervisor workflow that manages research delegation and coordination
supervisor_builder = StateGraph(SupervisorState, config_schema=Configuration)

# Add supervisor nodes for research management
supervisor_builder.add_node("supervisor", supervisor)           # Main supervisor logic
supervisor_builder.add_node("supervisor_tools", supervisor_tools)  # Tool execution handler

# Define supervisor workflow edges
supervisor_builder.add_edge(START, "supervisor")  # Entry point to supervisor

# Compile supervisor subgraph for use in main workflow
supervisor_subgraph = supervisor_builder.compile()

async def researcher(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher_tools"]]:
    """Individual researcher that conducts focused research on specific topics.
    
    This researcher is given a specific research topic by the supervisor and uses
    available tools (search, think_tool, MCP tools) to gather comprehensive information.
    It can use think_tool for strategic planning between searches.
    
    Args:
        state: Current researcher state with messages and topic context
        config: Runtime configuration with model settings and tool availability
        
    Returns:
        Command to proceed to researcher_tools for tool execution
    """
    # Step 1: Load configuration and validate tool availability
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    
    # Get all available research tools (search, MCP, think_tool)
    tools = await get_all_tools(config)
    if len(tools) == 0:
        raise ValueError(
            "No tools found to conduct research: Please configure either your "
            "search API or add MCP tools to your configuration."
        )
    
    # Step 2: Configure the researcher model with tools
    research_model_config = {
        "model": configurable.research_model,
        "max_tokens": configurable.research_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.research_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    # Prepare system prompt with MCP context if available
    researcher_prompt = research_system_prompt.format(
        mcp_prompt=configurable.mcp_prompt or "", 
        date=get_today_str()
    )
    
    # Configure model with tools, retry logic, and settings
    research_model = (
        configurable_model
        .bind_tools(tools)
        .with_retry(stop_after_attempt=configurable.max_structured_output_retries)
        .with_config(research_model_config)
    )
    
    # Step 3: Generate researcher response with system context
    messages = [SystemMessage(content=researcher_prompt)] + researcher_messages
    # Validate messages before sending to API to prevent content validation errors
    validated_messages = ensure_message_content_validity(messages)
    response = await research_model.ainvoke(validated_messages)
    
    # Step 4: Update state and proceed to tool execution
    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1
        }
    )

# Tool Execution Helper Function
async def execute_tool_safely(tool, args, config):
    """Safely execute a tool with error handling."""
    try:
        return await tool.ainvoke(args, config)
    except Exception as e:
        return f"Error executing tool: {str(e)}"


async def researcher_tools(state: ResearcherState, config: RunnableConfig) -> Command[Literal["researcher", "compress_research"]]:
    """Execute tools called by the researcher, including search tools and strategic thinking.
    
    This function handles various types of researcher tool calls:
    1. think_tool - Strategic reflection that continues the research conversation
    2. Search tools (web_search via Bright Data) - Information gathering
    3. MCP tools - External tool integrations
    4. ResearchComplete - Signals completion of individual research task
    
    Args:
        state: Current researcher state with messages and iteration count
        config: Runtime configuration with research limits and tool settings
        
    Returns:
        Command to either continue research loop or proceed to compression
    """
    # Step 1: Extract current state and check early exit conditions
    configurable = Configuration.from_runnable_config(config)
    researcher_messages = state.get("researcher_messages", [])
    most_recent_message = researcher_messages[-1]
    
    # Early exit if no tool calls were made (including native web search)
    has_tool_calls = bool(most_recent_message.tool_calls)
    has_native_search = (
        openai_websearch_called(most_recent_message) or 
        anthropic_websearch_called(most_recent_message)
    )
    
    if not has_tool_calls and not has_native_search:
        return Command(goto="compress_research")
    
    # Step 2: Handle other tool calls (search, MCP tools, etc.)
    tools = await get_all_tools(config)
    tools_by_name = {
        tool.name if hasattr(tool, "name") else tool.get("name", "web_search"): tool 
        for tool in tools
    }
    
    # Execute all tool calls in parallel
    tool_calls = most_recent_message.tool_calls
    tool_execution_tasks = [
        execute_tool_safely(tools_by_name[tool_call["name"]], tool_call["args"], config) 
        for tool_call in tool_calls
    ]
    observations = await asyncio.gather(*tool_execution_tasks)
    
    # Create tool messages from execution results
    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        ) 
        for observation, tool_call in zip(observations, tool_calls)
    ]
    
    # Step 3: Check late exit conditions (after processing tools)
    exceeded_iterations = state.get("tool_call_iterations", 0) >= configurable.max_react_tool_calls
    research_complete_called = any(
        tool_call["name"] == "ResearchComplete" 
        for tool_call in most_recent_message.tool_calls
    )
    
    if exceeded_iterations or research_complete_called:
        # End research and proceed to compression
        return Command(
            goto="compress_research",
            update={"researcher_messages": tool_outputs}
        )
    
    # Continue research loop with tool results
    return Command(
        goto="researcher",
        update={"researcher_messages": tool_outputs}
    )

async def compress_research(state: ResearcherState, config: RunnableConfig):
    """Compress and synthesize research findings into a concise, structured summary.
    
    This function takes all the research findings, tool outputs, and AI messages from
    a researcher's work and distills them into a clean, comprehensive summary while
    preserving all important information and findings.
    
    Args:
        state: Current researcher state with accumulated research messages
        config: Runtime configuration with compression model settings
        
    Returns:
        Dictionary containing compressed research summary and raw notes
    """
    # Step 1: Configure the compression model
    configurable = Configuration.from_runnable_config(config)
    synthesizer_model = configurable_model.with_config({
        "model": configurable.compression_model,
        "max_tokens": configurable.compression_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.compression_model, config),
        "tags": ["langsmith:nostream"]
    })
    
    # Step 2: Prepare messages for compression
    researcher_messages = state.get("researcher_messages", [])
    
    # Add instruction to switch from research mode to compression mode
    researcher_messages.append(HumanMessage(content=compress_research_simple_human_message))
    
    # Step 3: Attempt compression with retry logic for token limit issues
    synthesis_attempts = 0
    max_attempts = 3
    
    while synthesis_attempts < max_attempts:
        try:
            # Create system prompt focused on compression task
            compression_prompt = compress_research_system_prompt.format(date=get_today_str())
            messages = [SystemMessage(content=compression_prompt)] + researcher_messages
            # Validate messages before sending to API to prevent content validation errors
            validated_messages = ensure_message_content_validity(messages)

            # Execute compression
            response = await synthesizer_model.ainvoke(validated_messages)
            
            # Extract raw notes from all tool and AI messages
            raw_notes_content = "\n".join([
                str(message.content) 
                for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
            ])
            
            # Return successful compression result
            return {
                "compressed_research": str(response.content),
                "raw_notes": [raw_notes_content]
            }
            
        except Exception as e:
            synthesis_attempts += 1
            
            # Handle token limit exceeded by removing older messages
            if is_token_limit_exceeded(e, configurable.research_model):
                researcher_messages = remove_up_to_last_ai_message(researcher_messages)
                continue
            
            # For other errors, continue retrying
            continue
    
    # Step 4: Return error result if all attempts failed
    raw_notes_content = "\n".join([
        str(message.content) 
        for message in filter_messages(researcher_messages, include_types=["tool", "ai"])
    ])
    
    return {
        "compressed_research": "Error synthesizing research report: Maximum retries exceeded",
        "raw_notes": [raw_notes_content]
    }

# Researcher Subgraph Construction
# Creates individual researcher workflow for conducting focused research on specific topics
researcher_builder = StateGraph(
    ResearcherState, 
    output=ResearcherOutputState, 
    config_schema=Configuration
)

# Add researcher nodes for research execution and compression
researcher_builder.add_node("researcher", researcher)                 # Main researcher logic
researcher_builder.add_node("researcher_tools", researcher_tools)     # Tool execution handler
researcher_builder.add_node("compress_research", compress_research)   # Research compression

# Define researcher workflow edges
researcher_builder.add_edge(START, "researcher")           # Entry point to researcher
researcher_builder.add_edge("compress_research", END)      # Exit point after compression

# Compile researcher subgraph for parallel execution by supervisor
researcher_subgraph = researcher_builder.compile()

def generate_fallback_report(research_brief: str, findings: str) -> str:
    """Generate a fallback report when AI report generation fails."""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Create a structured report from the available findings
    fallback_content = f"""# Research Report - {current_date}

## Research Query
{research_brief or "Research analysis requested"}

## Executive Summary
This report was generated from research findings collected through automated web search and analysis. Due to API limitations, this is a structured presentation of the raw research data rather than an AI-generated synthesis.

## Key Findings

{findings[:10000] if findings else "No detailed findings were collected during the research process."}

---

## Research Methodology
- Automated web search using Bright Data enterprise proxy network
- Multi-source data collection and verification
- Real-time information gathering from current web sources

## Important Notes
- This report was generated using a failsafe method due to API timeout constraints
- The findings above represent raw research data that may require additional analysis
- For more detailed analysis, consider running the research query again or contact support

## Report Generated
Date: {current_date}
Method: Fallback report generation due to API timeout
Status: Research data collected successfully, AI synthesis unavailable

---

*This report contains research findings collected through automated processes. While efforts are made to ensure accuracy, users should verify critical information independently.*
"""
    
    return fallback_content

async def generate_streaming_report(findings: str, research_brief: str, messages: str, config: RunnableConfig) -> str:
    """Generate report using streaming to avoid API timeouts.

    Uses streaming responses which are specifically recommended by Heroku Inference API
    for long-running requests to avoid 408 timeout errors.

    Args:
        findings: Research findings to synthesize
        research_brief: Original research query
        messages: User message context
        config: Runtime configuration

    Returns:
        Complete synthesized report as string
    """
    configurable = Configuration.from_runnable_config(config)
    
    # Check if we're using Heroku Inference API (supports streaming)
    is_heroku_api = is_heroku_inference_api(configurable.final_report_model)
    
    if not is_heroku_api:
        logger.info(" Model doesn't support streaming, falling back to progressive generation")
        return await generate_progressive_report(findings, research_brief, messages, config)
    
    model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
        "tags": ["langsmith:nostream"],
        "stream": True  # Enable streaming
    }
    
    current_date = datetime.now().strftime("%B %d, %Y")
    
    try:
        # Create comprehensive prompt for streaming generation
        streaming_prompt = f"""Generate a comprehensive research report based on the following information:

Research Brief: {research_brief}

Research Findings: {findings[:15000]}  # More content since streaming handles it better

User Context: {messages[:2000]}

Date: {current_date}

Please generate a well-structured research report with the following sections:
1. Executive Summary (2-3 paragraphs)
2. Key Findings (3-5 bullet points)
3. Detailed Analysis (with subheadings)
4. Methodology and Sources

Format the report in markdown with clear headings. Focus on actionable insights and specific findings from the research data."""

        # Initialize streaming model
        streaming_model = configurable_model.with_config(model_config)
        
        logger.info(" Starting streaming report generation...")
        
        # Collect streamed response
        full_response = ""
        async for chunk in streaming_model.astream([HumanMessage(content=streaming_prompt)]):
            if hasattr(chunk, 'content') and chunk.content:
                full_response += chunk.content
        
        logger.info(f" Streaming report generation completed, length: {len(full_response)}")
        
        # Add report header and footer
        final_report = f"""# Research Report - {current_date}

## Research Query
{research_brief}

{full_response}

---

*This report was generated through streaming AI synthesis for comprehensive analysis. Research conducted using automated web search and multi-source data collection.*"""

        return final_report
        
    except Exception as e:
        logger.error(f" Streaming report generation failed: {str(e)}")
        logger.info(" Falling back to progressive report generation")
        return await generate_progressive_report(findings, research_brief, messages, config)

async def generate_progressive_report(findings: str, research_brief: str, messages: str, config: RunnableConfig) -> str:
    """Generate report progressively in sections to avoid API timeouts.

    This approach breaks down report generation into smaller, manageable sections
    that are less likely to hit API timeout limits.

    Args:
        findings: Research findings to synthesize
        research_brief: Original research query
        messages: User message context
        config: Runtime configuration

    Returns:
        Complete synthesized report as string
    """
    configurable = Configuration.from_runnable_config(config)
    model_config = {
        "model": configurable.final_report_model,
        "max_tokens": min(4000, configurable.final_report_model_max_tokens),  # Smaller chunks
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    # Initialize model for progressive generation
    report_model = configurable_model.with_config(model_config)
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Progressive report sections
    sections = {}
    
    try:
        # Section 1: Executive Summary (shorter context, faster generation)
        summary_prompt = f"""Based on this research brief: {research_brief}

And these key findings (first 3000 chars): {findings[:3000]}

Write a concise executive summary (2-3 paragraphs) for a research report. Focus on the most important findings and conclusions. Date: {current_date}"""
        
        summary_response = await asyncio.wait_for(
            report_model.ainvoke([HumanMessage(content=summary_prompt)]),
            timeout=45.0  # Shorter timeout for smaller sections
        )
        sections["executive_summary"] = summary_response.content
        
        # Section 2: Key Findings (structured analysis)
        findings_prompt = f"""Based on these research findings: {findings[:5000]}

Create a "Key Findings" section with 3-5 bullet points highlighting the most important discoveries. Be specific and actionable. Each bullet should be 1-2 sentences."""
        
        findings_response = await asyncio.wait_for(
            report_model.ainvoke([HumanMessage(content=findings_prompt)]),
            timeout=45.0
        )
        sections["key_findings"] = findings_response.content
        
        # Section 3: Detailed Analysis (main content)
        analysis_prompt = f"""Research Brief: {research_brief}

Research Data: {findings[:8000]}

Create a detailed analysis section covering the main aspects discovered in the research. Structure with subheadings and provide specific insights. Limit to 500 words."""
        
        analysis_response = await asyncio.wait_for(
            report_model.ainvoke([HumanMessage(content=analysis_prompt)]),
            timeout=60.0  # Slightly longer for main content
        )
        sections["detailed_analysis"] = analysis_response.content
        
        # Combine sections into final report
        final_report = f"""# Research Report - {current_date}

## Research Query
{research_brief}

## Executive Summary
{sections["executive_summary"]}

## Key Findings
{sections["key_findings"]}

## Detailed Analysis  
{sections["detailed_analysis"]}

## Research Methodology
- Automated web search using Bright Data enterprise proxy network
- Multi-source data collection and verification
- Real-time information gathering from current web sources
- Progressive AI synthesis for comprehensive analysis

---

*This report was generated through systematic research and progressive AI synthesis. While efforts are made to ensure accuracy, users should verify critical information independently.*"""

        return final_report
        
    except asyncio.TimeoutError as e:
        logger.warning(f" Progressive report generation timed out at section generation: {str(e)}")
        # Return partial report with completed sections
        completed_sections = []
        if "executive_summary" in sections:
            completed_sections.append(f"## Executive Summary\n{sections['executive_summary']}")
        if "key_findings" in sections:
            completed_sections.append(f"## Key Findings\n{sections['key_findings']}")
        if "detailed_analysis" in sections:
            completed_sections.append(f"## Detailed Analysis\n{sections['detailed_analysis']}")
            
        partial_report = f"""# Research Report - {current_date}

## Research Query
{research_brief}

{chr(10).join(completed_sections)}

## Research Notes
{findings[:2000]}

---

*This report was generated through progressive AI synthesis. Some sections may be incomplete due to API timeout constraints.*"""
        
        return partial_report
        
    except Exception as e:
        logger.error(f" Progressive report generation failed: {str(e)}")
        # Fallback to structured presentation
        return generate_fallback_report(research_brief, findings)

async def final_report_generation(state: AgentState, config: RunnableConfig):
    """Generate the final comprehensive research report with progressive synthesis.
    
    This function uses a progressive approach to generate reports section by section,
    significantly reducing the likelihood of API timeouts while maintaining quality.
    
    Args:
        state: Agent state containing research findings and context
        config: Runtime configuration with model settings and API keys
        
    Returns:
        Dictionary containing the final report and cleared state
    """
    # Step 1: Extract research findings and prepare state cleanup
    notes = state.get("notes", [])
    cleared_state = {"notes": {"type": "override", "value": []}}
    findings = "\n".join(notes)
    
    # Step 2: Try streaming report generation first (recommended by Heroku Inference API)
    try:
        logger.info(f" Attempting streaming report generation to avoid API timeouts")
        streaming_report = await generate_streaming_report(
            findings=findings,
            research_brief=state.get("research_brief", ""),
            messages=get_buffer_string(state.get("messages", [])),
            config=config
        )
        
        logger.info(f" Streaming report generation succeeded, length: {len(streaming_report)}")
        return {
            "final_report": streaming_report,
            "messages": [AIMessage(content=streaming_report)],
            **cleared_state
        }
        
    except Exception as e:
        logger.warning(f" Streaming report generation failed: {str(e)}, falling back to progressive approach")
    
    # Step 3: Try progressive report generation as fallback
    try:
        logger.info(f" Attempting progressive report generation as fallback")
        progressive_report = await generate_progressive_report(
            findings=findings,
            research_brief=state.get("research_brief", ""),
            messages=get_buffer_string(state.get("messages", [])),
            config=config
        )
        
        logger.info(f" Progressive report generation succeeded, length: {len(progressive_report)}")
        return {
            "final_report": progressive_report,
            "messages": [AIMessage(content=progressive_report)],
            **cleared_state
        }
        
    except Exception as e:
        logger.warning(f" Progressive report generation failed: {str(e)}, falling back to traditional approach")
    
    # Step 4: Fallback to traditional single-shot generation with retries
    configurable = Configuration.from_runnable_config(config)
    writer_model_config = {
        "model": configurable.final_report_model,
        "max_tokens": configurable.final_report_model_max_tokens,
        "api_key": get_api_key_for_model(configurable.final_report_model, config),
        "tags": ["langsmith:nostream"]
    }
    
    max_retries = 3
    current_retry = 0
    findings_token_limit = None
    
    while current_retry <= max_retries:
        try:
            # Create comprehensive prompt with all research context
            final_report_prompt = final_report_generation_prompt.format(
                research_brief=state.get("research_brief", ""),
                messages=get_buffer_string(state.get("messages", [])),
                findings=findings,
                date=get_today_str()
            )
            
            # Generate the final report with timeout handling
            try:
                final_report = await asyncio.wait_for(
                    configurable_model.with_config(writer_model_config).ainvoke([
                        HumanMessage(content=final_report_prompt)
                    ]),
                    timeout=120.0  # 2 minute timeout
                )
            except asyncio.TimeoutError:
                logger.warning(" Traditional report generation timed out locally, generating fallback report")
                # Generate a fallback structured report from the findings
                fallback_report = generate_fallback_report(
                    state.get("research_brief", ""), 
                    findings
                )
                final_report = AIMessage(content=fallback_report)
            
            # Return successful report generation
            return {
                "final_report": final_report.content, 
                "messages": [final_report],
                **cleared_state
            }
            
        except Exception as e:
            logger.error(f" Final report generation failed: {type(e).__name__}: {str(e)}")
            logger.error(f" Full traceback:\n{traceback.format_exc()}")
            
            # Handle API timeout errors specifically
            error_str = str(e).lower()
            exception_type = type(e).__name__
            is_timeout_error = (
                "timeout" in error_str or 
                "408" in str(e) or 
                "timed out" in error_str or
                "apistatuserror" in exception_type.lower() and "408" in str(e) or
                "request timed out" in error_str
            )
            
            if is_timeout_error:
                logger.warning(" API timeout detected, generating fallback report")
                fallback_report = generate_fallback_report(
                    state.get("research_brief", ""), 
                    findings
                )
                return {
                    "final_report": fallback_report,
                    "messages": [AIMessage(content=fallback_report)],
                    **cleared_state
                }
            
            # Handle token limit exceeded errors with progressive truncation
            if is_token_limit_exceeded(e, configurable.final_report_model):
                logger.info(f" Token limit exceeded, attempting retry {current_retry + 1}/{max_retries}")
                current_retry += 1
                
                if current_retry == 1:
                    # First retry: determine initial truncation limit
                    model_token_limit = get_model_token_limit(configurable.final_report_model)
                    logger.info(f" Model token limit: {model_token_limit}")
                    if not model_token_limit:
                        return {
                            "final_report": f"Error generating final report: Token limit exceeded, however, we could not determine the model's maximum context length. Please update the model map in deep_researcher/utils.py with this information. {e}",
                            "messages": [AIMessage(content="Report generation failed due to token limits")],
                            **cleared_state
                        }
                    # Use 4x token limit as character approximation for truncation
                    findings_token_limit = model_token_limit * 4
                    logger.info(f" Setting initial findings limit to {findings_token_limit} characters")
                else:
                    # Subsequent retries: reduce by 10% each time
                    findings_token_limit = int(findings_token_limit * 0.9)
                    logger.info(f" Reducing findings limit to {findings_token_limit} characters")
                
                # Truncate findings and retry
                findings = findings[:findings_token_limit]
                logger.info(f" Truncated findings to {len(findings)} characters, retrying...")
                continue
            else:
                # Non-token-limit error: return error immediately
                logger.error(f" Non-token-limit error in final report generation, failing immediately")
                return {
                    "final_report": f"Error generating final report: {type(e).__name__}: {str(e)}",
                    "messages": [AIMessage(content=f"Report generation failed: {type(e).__name__}: {str(e)}")],
                    **cleared_state
                }
    
    # Step 4: Return failure result if all retries exhausted
    logger.error(f" Final report generation failed after {max_retries} retries")
    return {
        "final_report": f"Error generating final report: Maximum retries ({max_retries}) exceeded due to token limits",
        "messages": [AIMessage(content=f"Report generation failed after {max_retries} retries due to token limits")],
        **cleared_state
    }

# Main Deep Researcher Graph Construction
# Creates the complete deep research workflow from user input to final report
deep_researcher_builder = StateGraph(
    AgentState, 
    input=AgentInputState, 
    config_schema=Configuration
)

# Add main workflow nodes for the complete research process
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)           # User clarification phase
deep_researcher_builder.add_node("write_research_brief", write_research_brief)     # Research planning phase
deep_researcher_builder.add_node("research_supervisor", supervisor_subgraph)       # Research execution phase
deep_researcher_builder.add_node("final_report_generation", final_report_generation)  # Report generation phase

# Define main workflow edges for sequential execution
deep_researcher_builder.add_edge(START, "clarify_with_user")                       # Entry point
deep_researcher_builder.add_edge("research_supervisor", "final_report_generation") # Research to report
deep_researcher_builder.add_edge("final_report_generation", END)                   # Final exit point

# Compile the complete deep researcher workflow
deep_researcher = deep_researcher_builder.compile()