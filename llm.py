from tools import TOOL_SCHEMAS
import os
import time

from rich.console import Console
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

SYSTEM_PROMPT = f"""
You are a coding agent. Your job is to code, Always code.
Use the bash tool to inspect files.
Answer back to the user once exploration is done.

You can browse the web with the agent-browser CLI via the bash tool:
agent-browser open <url>, agent-browser snapshot -i,
agent-browser click @eN, agent-browser fill @eN "text",
agent-browser get text @eN, agent-browser close.
Run snapshot after each navigation.

Your current working directory is {os.getcwd()}
The current date is (%d/%m/%Y): {time.strftime("%d/%m/%Y", time.localtime())}
"""


def call_llm(messages):
    with Console().status("Thinking..."):
        response = client.chat.completions.create(
            model="q38",
            messages=messages,
            tools=TOOL_SCHEMAS,
        )

    message = response.choices[0].message

    completion_details = response.usage.completion_tokens_details
    prompt_details = response.usage.prompt_tokens_details

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
        "cached_tokens": getattr(prompt_details, "cached_tokens", None),
    }

    return message, usage


# with Console().status("Thinking..."):
#     response = client.chat.completions.create(
#         model="q38",
#         messages=[
#             {"role": "system", "content": SYSTEM_PROMPT},
#             {"role": "user", "content": user_input}
#         ],
#         tools=TOOL_SCHEMAS
#     )

# message = response.choices[0].message
# output = response.choices[0].message.content

# completion_details = response.usage.completion_tokens_details
# prompt_details = response.usage.prompt_tokens_details


# print("\nAgent: ", output, "\n")

# if message.tool_calls:
#     try:
#         tool_call = message.tool_calls[0]
#         fn_name = tool_call.function.name
#         args = json.loads(tool_call.function.arguments)
#         result = TOOLS[fn_name](**args)

#         print("Reasoning: ", getattr(message, "reasoning", None))
#         print(f"Tool: {fn_name}({args})")
#         print(result, "\n")

#     finally:
#         print(TOOLS["bash"]("agent-browser close"), "\n")

# print(json.dumps(response.model_dump(), indent=2))
