import json

"""
import argparse

need to add each of these below that are missing
from . import commands
from . import compact
from . import history
from . import session
from .context import reminder
from .llm import SYSTEM_PROMPT, call_llm
from . import sandbox
from .todos import active_form
from .tools import execute
from .ui import ui
"""

from llm import SYSTEM_PROMPT, call_llm
from tools import TOOLS

MAX_STEPS = 25

user_input = input("Enter your agent prompt> ")

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": user_input},
]

for step in range(MAX_STEPS):
    message, usage = call_llm(messages)
    messages.append(message.model_dump(exclude_none=True))

    if message.content:
        print("\nAgent: ", message.content, "\n")

    print(usage)

    if not message.tool_calls:
        break

    for tool_call in message.tool_calls:
        args = json.loads(tool_call.function.arguments)
        result = TOOLS[tool_call.function.name](**args)
        print(f"Tool: {tool_call.function.name}({args})")
        print(result, "\n")

        messages.append(
            {"role": "tool", "tool_call_id": tool_call.id, "content": result}
        )
