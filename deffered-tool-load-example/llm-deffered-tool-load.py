import json
import tools

from rich.console import Console
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

SYSTEM_PROMPT = """
You are a coding agent. Your job is to code, Always code.
You have access to various tools to enable you to run shell commands, access a web browser and much more.
If a request calls for some sort of action, you can call search_tools(search_term) to see what tools are available to you,
then load_tool(tool_name) to load that tools schema.
"""

SEARCH_TOOLS = {
    "type": "function",
    "function": {
        "name": "search_tools",
        "description": "Print a list of available tools and descriptions",
        "parameters": {
            "type": "object",
            "properties": {
                "search_term": {
                    "type": ["string", "null"],
                    "description": "Optional search term to narrow down returned tool list"
                }
            }
        }
    }
}

def search_tools(search_term=None):
    hits = [f"{n}: {t['summary']}" for n, t in tools.REGISTRY.items()
            if not search_term or search_term.lower() in (n + " " + t["summary"]).lower()]
    return "\n".join(hits) or "no matching tools"

LOAD_TOOL = {
    "type": "function",
    "function": {
        "name": "load_tool",
        "description": "Load a schema for a tool",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "The name of the tool you want to load"
                }
            },
            "required": ["tool_name"]
        }
    }
}

active = [SEARCH_TOOLS, LOAD_TOOL]   # passed as tools=active on every call

def load_tool(tool_name):
    entry = tools.REGISTRY.get(tool_name)
    if entry is None:
        return f"error: unknown tool {tool_name!r}. Available: {', '.join(tools.REGISTRY)}"
    if entry["schema"] not in active:
        active.append(entry["schema"])
    return f"loaded {tool_name}, you can call it now"


user_input = input("Enter your prompt> ")

with Console().status("Thinking..."):
    response = client.chat.completions.create(
        model="q38",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_input}
        ],
        tools=active
    )

message = response.choices[0].message
output = response.choices[0].message.content

completion_details = response.usage.completion_tokens_details
prompt_details = response.usage.prompt_tokens_details

usage = {
    "prompt_tokens": response.usage.prompt_tokens,
    "completion_tokens": response.usage.completion_tokens,
    "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
    "cached_tokens": getattr(prompt_details, "cached_tokens", None)
}

print("\nAgent: ", output, "\n")

if message.tool_calls:
    try:
        tool_call = message.tool_calls[0]
        fn_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments or "{}")

        FUNCS = {"search_tools": search_tools, "load_tool": load_tool}
        FUNCS.update({n: t["fn"] for n, t in tools.REGISTRY.items()})

        loaded = {t["function"]["name"] for t in active}

        fn = FUNCS.get(fn_name)
        if fn is None:
            result = f"error: unknown tool {fn_name!r}"
        elif fn_name not in loaded:
            result = f"error: tool {fn_name!r} is not loaded. Call load_tool({fn_name!r}) first."
        else:
            result = fn(**args)

        print("Reasoning: ", getattr(message, "reasoning", None))
        print(f"Tool: {fn_name}({args})")
        print(result, "\n")

    finally:
        print(tools.bash("agent-browser close"), "\n")

print(usage)
print(json.dumps(response.model_dump(), indent=2))