"""Shared test fixtures for lingdiag tests."""

import pytest

from lingdiag.patterns import AgentConfig, ToolDef


@pytest.fixture
def empty_config():
    return AgentConfig()


@pytest.fixture
def clean_tools_config():
    """A well-configured agent with clear tool descriptions."""
    return AgentConfig(
        tools=[
            ToolDef(
                name="get_weather",
                description="Retrieve current weather conditions for a specific city. Use this for CURRENT weather only — use get_forecast for future predictions.",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name with optional country code (e.g., 'London, UK')",
                        },
                    },
                    "required": ["city"],
                },
            ),
            ToolDef(
                name="get_forecast",
                description="Retrieve a multi-day weather forecast for a specific city. Use this for FUTURE weather predictions — use get_weather for current conditions.",
                parameters={
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name with optional country code",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Number of days to forecast (1-7)",
                        },
                    },
                    "required": ["city"],
                },
            ),
        ],
        system_prompt=(
            "# Weather Bot v1.0\n\n"
            "You are a weather assistant. Each user message is an independent query.\n"
            "PRIORITY 1: Only report data from the API.\n"
            "PRIORITY 2: Respond in plain text, 2-3 sentences maximum.\n"
            "Maximum 3 tool calls per query. If lookup fails, retry once then report the error.\n"
        ),
        constraints={"max_iterations": 3, "timeout": 30},
    )


@pytest.fixture
def bad_tools_config():
    """Agent with vague, overlapping tool descriptions."""
    return AgentConfig(
        tools=[
            ToolDef(name="get_data", description="Get data", parameters={"type": "object", "properties": {"data": {"type": "string"}}}),
            ToolDef(name="fetch_data", description="Get data from the system", parameters={"type": "object", "properties": {"input": {"type": "string"}}}),
            ToolDef(name="handle_request", description="Handle the user request", parameters={"type": "object", "properties": {"value": {"type": "string"}}}),
            ToolDef(name="no_desc_tool", description="", parameters={}),
        ],
        system_prompt="You are an assistant. Help the user.",
    )


@pytest.fixture
def bad_prompt_config():
    """Agent with problematic system prompt."""
    return AgentConfig(
        system_prompt=(
            "You are a helpful assistant. Be concise but thorough. Don't apologize. "
            "Never make things up. Avoid guessing. Use common sense.\n\n"
            "If a task fails, keep trying until it works. Don't stop until done.\n\n"
            "Remember everything the user says. Use all conversation history.\n"
            "Always keep track of previous interactions.\n\n"
            "Respond in JSON when the data is structured. Use markdown for text. "
            "XML is also acceptable.\n\n"
            "Some more instructions here to make this prompt long enough.\n"
            "And a few more lines to cross the threshold.\n"
            "This is quite a lengthy prompt without version markers.\n"
            "Additional context and rules follow.\n"
            "Rule about this. Rule about that. Rule about the other thing.\n"
            "More rules. Even more rules. Rules upon rules.\n"
        ),
        tools=[
            ToolDef(name="search", description="Search for things", parameters={}),
        ],
    )


@pytest.fixture
def bad_messages_config():
    """Agent with problematic message sequence."""
    return AgentConfig(
        messages=[
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
            {"role": "user", "content": "Also this"},
            {"role": "system", "content": "Be nice."},
            {"role": "assistant", "content": "Sure!"},
            {"content": "orphan message"},
            {"role": "assistant", "content": "More"},
            {"role": "assistant", "content": "Even more"},
            {"role": "tool", "content": "{}"},
            {"role": "user", "content": "OK"},
        ],
    )
