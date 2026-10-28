import subprocess


def bash(command: str) -> str:
    """Run a shell command and return its combined stdout and stderr"""
    try:
        done = subprocess.run(
            command, shell=True, text=True, capture_output=True, timeout=30
        )
    except subprocess.TimeoutExpired as expired:
        return (
            f"Timed out after {expired.timeout}s and was killed. "
            "Narrow it down - search inside the working directory rather than /."
        )

    return done.stdout + done.stderr


def read_file(path: str) -> str:
    """Read a file and return its contents"""
    with open(path, "r") as f:
        return f.read()


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command and return its output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to run",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file and return its contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                    },
                },
                "required": ["path"],
            },
        },
    },
]

TOOLS = {"bash": bash, "read_file": read_file}
