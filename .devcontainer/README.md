# Dev container

A container that acts as the security boundary, so Claude can run with permission
prompts disabled without having reach over the host.

New to dev containers, or want the VS Code commands and lifecycle hooks in one page?
See [CHEATSHEET.md](CHEATSHEET.md).

## Use it

1. Install Docker Desktop and the VS Code [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers).
2. Open the repo in VS Code, then **Dev Containers: Reopen in Container** from the
   command palette. First build takes a few minutes.
3. In the container terminal, run `claude` and sign in once. The credentials live in
   a named volume, so rebuilds don't log you out.
4. For unattended work, run `yolo` (aliased to `claude --dangerously-skip-permissions`).

The alias is deliberate rather than a default: normal `claude` sessions still honour
the repo's `auto` permission mode from [.claude/settings.json](../.claude/settings.json),
and you opt into bypass by typing a different command.

## What contains what

**Filesystem.** Only this repository is bind-mounted, at `/workspaces/pysenscritique`.
Edits appear on the host immediately, so Claude can still rewrite any file in this
repo without asking. Nothing else on the host is reachable: no `~/.ssh`, no cloud
credentials, no other repos. That is the main thing the container buys you.

**Network.** [project-firewall.sh](project-firewall.sh) installs a default-deny
egress firewall (iptables + ipset) at container create and at every start. Allowed:
DNS, loopback, the host network (so the editor can talk to the container), outbound
SSH, GitHub's published IP ranges, and the domains listed at the top of the script,
which cover Claude Code, PyPI, the VS Code marketplace, and SensCritique. Everything
else is rejected. This is what stops a prompt-injected session from exfiltrating to
an arbitrary host.

**Root.** The container runs as `vscode`. The image's blanket passwordless sudo is
removed and replaced with a single rule allowing only `project-firewall.sh`, so a
bypassed session cannot flush the rules it is confined by. `/usr/local/bin` is
root-owned, so the script behind that rule cannot be swapped either.

## Your skills, commands and subagents

Your personal `~/.claude/skills`, `~/.claude/commands`, `~/.claude/agents` and global
`~/.claude/CLAUDE.md` are bind-mounted in **read-only**. Read-only matters: those files
execute on the host in your other sessions, so a bypassed container session must not be
able to rewrite them and wait for you to run them outside the box. Everything else in
`~/.claude` is the container's own volume, so container auth and history stay separate
from the host's.

`HOME` is `/home/vscode` and `CLAUDE_CONFIG_DIR` is `/home/vscode/.claude`, deliberately
the same directory, so it doesn't matter whether Claude Code resolves user config via
`$HOME/.claude` or `$CLAUDE_CONFIG_DIR`. Both land on the mounted content.

Consequences worth knowing:

- Editing a skill from inside the container fails. Edit it on the host.
- Skills that drive macOS or host-only tooling won't work here, because the container is
  Linux and has no Homebrew, Ansible, `mas`, or your host `~/src`. That covers
  `install-software`, `check-orphan-brew`, `md-to-pdf`, and `create-code-project`.
  Repo-scoped ones like `commit` and `precommit` work fine.
- Project-level `.claude/` comes in through the workspace bind mount, so this repo's
  settings and any project skills work with no extra setup.
- Plugins aren't mounted, since Claude Code writes to that directory. Install them inside
  the container with `claude plugin` and they persist in the volume across rebuilds.
- If you add `~/.claude/hooks`, mount it the same way. Note that hooks run commands, so
  a host-authored hook will execute inside the container.

Because these are host paths, all four must exist on the host or the container won't
start. Create empty directories for any you don't have.

## Limits worth knowing

Claude's own credentials sit in `~/.claude` inside the container, and a malicious
repo could read them. Use this for repos you trust, which for a personal project
means: it protects you from Claude's mistakes and from injected content in API
responses, not from a determined supply-chain attacker. Don't mount host secrets in.

## Expected noise in the logs

Microsoft's telemetry endpoint `mobile.events.data.microsoft.com` is not allowlisted, so
the VS Code server retries it and logs `EHOSTUNREACH` every couple of minutes in
`~/.vscode-server/data/logs/*/remoteagent.log`. That is the firewall doing its job, not a
fault. Same for any other unlisted host: the failure mode is a fast `EHOSTUNREACH` or
`REJECT`, so if something in the container mysteriously cannot reach the network, check
that log and then this allowlist.

## Adding a domain

Add it to `ALLOWED_DOMAINS` in [project-firewall.sh](project-firewall.sh) and rebuild,
or for a one-off, edit and re-run `sudo /usr/local/bin/project-firewall.sh`.

Domains are resolved to IPs when the script runs. If a CDN rotates addresses and a
host goes unreachable mid-session, re-running the script re-resolves everything. The
script is idempotent and safe to run repeatedly.

Two gotchas, both already handled, but worth knowing if you edit the script:

- Don't rename it to `init-firewall.sh`. The `claude-code` dev container feature
  installs its own script under that name, and features run after the Dockerfile,
  so it would silently overwrite this one.
- `iptables -F` clears rules but not the default policy, so the script explicitly
  resets policies to ACCEPT before it resolves domains. Without that, a second run
  would be locked out of DNS and `api.github.com` by its own leftover DROP policy.

## Python setup

The venv lives at `/home/vscode/.venv` (`UV_PROJECT_ENVIRONMENT`), not in the
workspace, so the container's Linux venv and the host's macOS `.venv` don't collide.
`make install` runs on create; `make check` works as usual. The uv download cache is
a named volume, so rebuilds are fast.
