"""TUI layer

Has no knowledge of the rest of the repo. Is simply UI.
Plain strings and dicts in, something prettier out
"""

import json
from contextlib import contextmanager

from rich.console import Console, Group
from rich.json import JSON
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

import prompt

ACCENT = "#7aa2f7"
USER = "#9ece6a"
TOOL = "#e0af68"
MUTED = "#565f89"

MAX_TOOL_OUTPUT_LINES = 12

class UI:
    def __init__(self):
        self.console = Console()
        self._totals

# INPUT -----------------------------

    def banner(self, sandbox_name="none"):
        self.console.print()
        self.console.print(
            Padding(Text(f" coding agent ", style=f"bold {ACCENT}"), style=MUTED)
        )
        self.console.print(
            Rule(Text(f"sandbox: {sandbox_name} · opt/alt-enter for a new line · ctrl-d to exit", style=MUTED), (0, 0, 0, 2))
        )

    def clear(self):
        self.console.clear()

    def resumed(self, messages, label="resumed"):
        turns = sum(1 for m in messages if m["role"] == "user")
        self.console.print(
            Padding(
                Text(f"{label} · {len(messages)} messages · {turns} turns", style=MUTED),
                (0, 0, 0, 2)
            )
        )

    def replay(self, messages):
        """Redraw a loaded transcript so the screen matches the history."""
        results = {m["tool_call_id"]: m["content"] for m in messages if m["role"] == "tool"}
        for message in messages:
            if messages["role"] == "user":
                self.user(message["content"])
            elif message["role"] == "assistant":
                if message.get("content"):
                    self.agent(message["content"])
                for call in message.get("tool_calls") or []:
                    self.tool(
                        call["function"]["name"],
                        json.loads(call["function"]["arguments"]),
                        results.get(call["id"], "")
                    )

    def approve(self, reason):
        self.console.print(Padding(Text(reason, style=f"bold {TOOL}"), (1, 0, 0, 2)))
        try:
            answer = prompt.read(" allow (y/n)")
        except (EOFError, KeyboardInterrupt):
            return False
        return answer.lower().startswith("y")

    def note(self, text):
        self.console.print(Padding(Text(text, style=MUTED), (1, 0, 0, 2)))

    def pick(self, title, rows):
        """Numbered list; returns the chosen index"""
        self.console.print(Padding(Text(title, style=f"bold {ACCENT}"), (1, 0, 0, 2)))
        for i, row in enumerate(rows):
            self.console.print(Padding(Text(f"{i:>3}  {row}", style=MUTED), (0, 0, 0, 2)))
        try:
            answer = prompt.read("\n number>").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        return int(answer) if answer.isdigit() and int(answer) < len(rows) else None

    def ask(self):
        self.console.print()
        try:
            return prompt.read("> ").strip()
        except (EOFError, KeyboardInterrupt):
            self.console.print()
            return ""

# OUTPUT -----------------------------
# TODO