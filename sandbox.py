"""Linux sandbox for bash tool calls, built on bubblewrap.

Policy: read anything, write only inside the project (not .git), no network.

Requirements:
Install bubblewrap from the distro package: sudo apt install bubblewrap
"""

import os
import shutil
import signal
import subprocess
from functools import lru_cache
from pathlib import Path

PROJECT = Path.cwd().resolve()
MAX_OUTPUT = 100_000
# Directories under $HOME replaced by an empty tmpfs. Extend as needed.
HIDE_DIRS = [".ssh", ".aws", ".gnupg", ".config/gh", ".kube", ".docker"]


class SandboxUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def available():
    """True only if bwrap exists AND the kernel lets us create namespaces."""
    if not shutil.which("bwrap"):
        return False
    probe = subprocess.run(
        ["bwrap", "--ro-bind", "/", "/", "--unshare-all", "true"],
        capture_output=True,
    )
    return probe.returncode == 0


def name():
    return "bubblewrap" if available() else "none"


def _clean_path():
    """Host PATH minus Windows entries (/mnt/c/...), which WSL appends."""
    parts = os.environ.get("PATH", "/usr/bin:/bin").split(":")
    return ":".join(p for p in parts if not p.startswith("/mnt/")) or "/usr/bin:/bin"


def wrap(command):
    if not available():
        raise SandboxUnavailable("bwrap missing or namespaces not permitted")

    args = [
        "bwrap",
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",
    ]
    if not str(PROJECT).startswith("/mnt/"):
        args += ["--tmpfs", "/mnt"]  # hide the Windows drives (WSL2)
    if Path("/run/WSL").is_dir():
        args += ["--tmpfs", "/run/WSL"]  # hide the WSL interop sockets
    hidden = set()
    for d in HIDE_DIRS:
        real = (
            Path.home() / d
        ).resolve()  # follow symlinks: bwrap mounts on the target
        if not real.is_dir():
            continue
        if not str(PROJECT).startswith("/mnt/") and str(real).startswith("/mnt/"):
            continue  # target is under /mnt, already hidden above
        hidden.add(real)
    for real in sorted(hidden):
        args += ["--tmpfs", str(real)]  # empty dir over credentials
    args += ["--bind", str(PROJECT), str(PROJECT)]
    git = PROJECT / ".git"
    if git.exists():
        args += ["--ro-bind", str(git), str(git)]  # must come after the --bind above
    args += [
        "--unshare-all",  # user, ipc, pid, net, uts, cgroup
        "--new-session",  # blocks terminal (TIOCSTI) injection
        "--die-with-parent",
        "--clearenv",
        "--setenv",
        "PATH",
        _clean_path(),
        "--setenv",
        "HOME",
        "/tmp",
        "--setenv",
        "TERM",
        "dumb",
        "--chdir",
        str(PROJECT),
        "/bin/sh",
        "-c",
        command,
    ]
    return args


def run(command, timeout=60):
    proc = subprocess.Popen(
        wrap(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,  # own process group so we can kill the lot
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        err += f"\n[killed after {timeout}s]"
        code = 124
    return subprocess.CompletedProcess(
        proc.args, code, out[:MAX_OUTPUT], err[:MAX_OUTPUT]
    )
