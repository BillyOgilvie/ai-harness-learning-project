import subprocess

def bash(command):
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr

BASH_TOOL = {
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
                }
            },
            "required": ["command"]
        }
    }
}

REGISTRY = {
    "bash": {"summary": "Run a shell command.", "schema": BASH_TOOL, "fn": bash}
}