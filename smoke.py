import time
import json
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

tools = [
    {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two integers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
        },
    }
]

t = time.time()

resp = client.chat.completions.create(
    model="q38",
    messages=[{"role": "user", "content": "What is 1234 + 5678? Use the tool."}],
    tools=tools,
)

pretty_json = json.dumps(resp.choices[0].message.model_dump(), indent=2)
useage_pretty_json = resp.usage.model_dump_json(indent=2)

print(f"Time Taken: {round(time.time() - t, 1)} seconds")
print(f"Response:\n{pretty_json}")
print(f"Useage:\n{useage_pretty_json}")
