# How the Harness Sandbox Works

Oct 30, 2026 · @Billy Keeling-Ogilvie

The sandbox runs every command the model asks for inside a bubblewrap jail that can read your machine, write only to the project folder, and reach nothing else.

## What the sandbox is for

The harness gives the model a bash tool, and whatever the model types runs with your permissions. One bad command is enough: a mistaken `rm -rf`, a script that reads `~/.ssh` and sends it out, or an instruction hidden in a web page that tells the model to do either.

The sandbox limits what a command can do once it runs. It is aimed at accidents and injected instructions. It does not stop an attacker with a kernel exploit, because a sandboxed process shares your machine's kernel. That last point is my understanding of how Linux namespaces work, not something the bubblewrap man page says.

## The policy and how each rule is enforced

One policy, enforced by the kernel through bubblewrap options: read anything, write only inside the project, no network, a clean environment, and a short list of places hidden entirely.

| Rule | Mechanism | What a command sees |
| --- | --- | --- |
| Read the whole filesystem | `--ro-bind / /` | Everything, read-only |
| Write only in the project | `--bind PROJECT PROJECT` | The project folder is writable. Writes elsewhere fail with "Read-only file system" |
| Protect `.git` | `--ro-bind .git .git` after the project bind | History is readable. Commits and config changes fail |
| Private scratch space | `--tmpfs /tmp` | A fresh empty `/tmp`, discarded afterwards |
| No network | `--unshare-all`, which includes a new network namespace | Connections fail with "Network is unreachable" |
| Clean environment | `--clearenv` plus three `--setenv` | Only `PATH`, `HOME=/tmp` and `TERM=dumb`. API keys in your shell are gone |
| Hide Windows and secrets | Empty tmpfs over `/mnt`, `/run/WSL`, `~/.ssh`, `~/.aws` and others | Empty directories where those were |
| Isolated processes | `--unshare-all` (new PID namespace) and `--new-session` | Only its own processes, and no controlling terminal |

The "What a command sees" column was observed in the verification runs, not just read from the docs.

## How bubblewrap builds the jail

bwrap starts your command in a new, empty filesystem whose root is a tmpfs, then builds the tree from the mount options you give it. The man page says filesystem options are applied in the order given, so later mounts sit on top of earlier ones.

This is the order `wrap()` issues them in:

1. `--ro-bind / /` puts the whole host filesystem in, read-only. Everything after it overrides part of this.
2. `--dev /dev` and `--proc /proc` add a device tree and a procfs. The procfs lists only processes in the new PID namespace, so a command sees a handful (4 in the test).
3. `--tmpfs /tmp` covers the host's `/tmp` with an empty one.
4. `--tmpfs /mnt` hides the Windows drives. It is skipped when the project itself lives under `/mnt`.
5. `--tmpfs /run/WSL` hides the interop sockets, when that directory exists.
6. `--tmpfs` over each existing credential directory.
7. `--bind PROJECT PROJECT` opens the one writable window.
8. `--ro-bind PROJECT/.git PROJECT/.git` closes part of that window again.

After the mounts come `--unshare-all` (all possible namespaces, per the man page), `--new-session`, `--die-with-parent`, `--clearenv`, three `--setenv` options, `--chdir` to the project, and finally `/bin/sh -c <command>`.

### Why the order matters

Step 8 has to come after step 7. A read-only mount placed before the project bind would be covered by it, and `.git` would be writable. The `/mnt` tmpfs also has to go before the project bind, but if the project lives under `/mnt`, hiding `/mnt` would remove the project's own path. That is why `wrap()` skips step 4 in that case.

### Mounts land on the real path

On your machine `~/.aws` is a symlink to `/mnt/c/Users/billy/.aws`. In the second version the `/mnt` tmpfs was already in place, so the target no longer existed and bwrap stopped with "Can't mount tmpfs ... No such file or directory". `wrap()` now resolves each directory first and skips any whose real path is under `/mnt`, since those are already hidden.

The man page does not say whether bind mounts are recursive. In your first run `/mnt/c` was readable inside the sandbox after `--ro-bind / /`, so the Windows mount came along with the root bind.

## Walking through sandbox.py

The file is about 100 lines in five parts. Python features are explained where they first appear.

### Setup

```python
PROJECT = Path.cwd().resolve()
MAX_OUTPUT = 100_000
HIDE_DIRS = [".ssh", ".aws", ".gnupg", ".config/gh", ".kube", ".docker"]
```

`PROJECT` is fixed once, at import, to wherever the process was started. `Path` from `pathlib` is an object for file paths, and `.resolve()` makes it absolute and follows symlinks. If the harness later changes directory, `PROJECT` does not follow.

`100_000` is just 100000; Python allows underscores in numbers. `class SandboxUnavailable(RuntimeError): pass` defines a new exception type with no new behaviour. Its job is to give the caller a name to catch.

### available()

It runs the smallest possible sandbox, `bwrap --ro-bind / / --unshare-all true`, and checks the exit code. 0 means bwrap is installed and the kernel lets you create namespaces. `shutil.which` looks a program up on `PATH` and returns `None` if it is missing.

`@lru_cache(maxsize=1)` is a decorator that remembers the return value, so the probe runs once per process instead of once per command.

### \_clean\_path()

WSL appends Windows folders to `PATH`. This splits the host `PATH` on `:`, drops entries under `/mnt/`, and joins the rest. The `for ... if ...` inside `join` is a generator expression, a compact filtered loop. The trailing `or` supplies a default if nothing is left.

### wrap()

It builds the full bwrap command as a list of strings. Each element reaches bwrap as one argument, so there is no shell quoting on the host side. The model's `command` string goes to `/bin/sh -c` inside the sandbox, which is the only place shell parsing happens.

If `available()` is false, `wrap()` raises `SandboxUnavailable`. The video's version returned `None`, and `run()` then ran the command unsandboxed. This one fails closed. The caller has to handle the error, for example by returning it to the model as the tool result, and nothing runs.

Smaller Python points: `args += [...]` extends a list in place, and `Path.home() / d` joins paths with the `/` operator. `hidden` is a set, which drops duplicates when two entries resolve to the same real directory, and `sorted()` makes the order stable.

### run()

```python
try:
    out, err = proc.communicate(timeout=timeout)
    code = proc.returncode
except subprocess.TimeoutExpired:
    os.killpg(proc.pid, signal.SIGKILL)
    out, err = proc.communicate()
    code = 124
```

`Popen` starts the process and returns straight away, unlike `subprocess.run`, which waits. `communicate(timeout=...)` waits, collects stdout and stderr, and raises `TimeoutExpired` if time runs out. `start_new_session=True` puts bwrap in its own process group so `os.killpg` can signal the whole group. 124 is the exit code GNU `timeout` uses.

The return value is a `subprocess.CompletedProcess`, the same shape `subprocess.run` returns, so callers read `.stdout`, `.stderr` and `.returncode`. Output is cut to `MAX_OUTPUT` characters.

The test shows nothing survives a timeout: no `sleep` was left after 2.0 seconds. It does not show why. `--new-session` gives the sandbox its own session, so the group kill probably reaches only bwrap. The man page says `--die-with-parent` kills the sandbox processes when bwrap's parent dies, and a PID namespace ends when its first process does. I have not isolated which of these does the work.

## How we know it works

`verify_sandbox.py` makes a throwaway project folder in your home directory, runs each check through `sandbox.run`, prints a table, then prints the same results as JSON to paste back. Three rules in it came from things that went wrong:

- **Controls.** A check that expects something to be blocked first does the same action without the sandbox. If the control fails, the check after it means nothing.
- **Preflight.** It runs `echo sbxok` in the sandbox before anything else and stops if that fails, printing bwrap's own error.
- **Sentinel.** Blocked-expected checks end their command with `echo __sbx_ran__` and require that text in the output. Without it, a sandbox that never started looks like one that blocked everything.

| Run | Files | Result | What it showed |
| --- | --- | --- | --- |
| 1 | v1 | 15 PASS (12 checks, 3 controls) | Every check passed, but the INFO probes showed `powershell.exe` running inside the sandbox and `~/.ssh` listed. |
| 2 | v2 | Void | bwrap failed to start on `~/.aws`. Six checks printed PASS only because nothing ran. |
| 3 | v3 | 20 PASS (15 checks, 5 controls) | Clean. Listing `/run/WSL` by hand then showed seven interop sockets inside. |
| 4 | v4 | 22 PASS (16 checks, 6 controls) | Clean. `/mnt/c` and the sockets are gone from inside. |

A pass proves only what its check tests. "Interop sockets hidden" shows the sockets are out of sight, not that they were exploitable. All four runs were on one machine, WSL2 Ubuntu with Python 3.12.3, on 29 October 2026.

## What it does not cover yet

- **Syscalls.** There is no seccomp filter; the sandbox reported `Seccomp: 0`. The man page recommends seccomp to block the `TIOCSTI` ioctl. `--new-session` is the cover we have instead.
- **Readable secrets.** Read-anything is the policy, so other projects, shell history and token files such as `~/.npmrc` and `~/.netrc` are readable. `--tmpfs` works only on directories, so a file would need a read-only bind of `/dev/null` over it. I have not tested that.
- **Network.** It is all or nothing. `pip install` and `git clone` fail inside, so dependencies have to be installed from outside.
- **Git writes.** `.git` is read-only, so `git commit` and `git checkout` fail inside. If the harness needs them, they have to run outside the sandbox.
- **Other sockets.** Unix sockets under `/run` other than `/run/WSL` have not been examined.
- **Output size.** `communicate()` holds all output in memory before the 100,000 character cut, so a command that prints gigabytes fills memory first.
- **The kernel.** Sandboxed commands share it with everything else, so a kernel bug is outside what this protects against. This is my understanding, not something the man page states.
- **Fixed project path.** `PROJECT` is set at import and does not follow later `chdir` calls.

## Where to read next

I opened only the first of these. The rest I saw in search results and have not read in full.

- [bwrap(1) man page](https://manpages.debian.org/testing/bubblewrap/bwrap.1) on Debian covers every flag used here.
- [Codex sandboxing docs](https://developers.openai.com/codex/concepts/sandboxing) describe the macOS, Linux and Windows approaches side by side.
- [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) adds proxy-based network allowlisting on top of bubblewrap.
- [hozo](https://pypi.org/project/hozo/) has an `hozo explain` command that prints the bwrap arguments it would use, which is handy for comparing against `wrap()`.
- Codex's Linux code is in `codex-rs/linux-sandbox/src/bwrap.rs`. That path came from a pull request diff and I have not opened the file.

A good exercise once the harness works is to line up the mount list in `wrap()` against Codex's and see what it mounts or hides that this version does not.
