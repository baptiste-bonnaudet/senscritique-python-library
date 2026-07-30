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

**Filesystem.** Only this repository is bind-mounted, at `/workspaces/senscritique-python-library`.
Edits appear on the host immediately, so Claude can still rewrite any file in this
repo without asking. Beyond that and the read-only Claude config and git identity
mounts described below, nothing else on the host is reachable: no cloud credentials,
no other repos, no rest of `~/.ssh`. That is the main thing the container buys you.

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

## Git identity and signing

Committing from the container needs three things the base image has none of: a name
and email, a signing key, and an SSH key for pushing. Two mounts supply them, and
[setup-git-identity.sh](setup-git-identity.sh) wires them up at create.

- `~/.gitconfig` mounts read-only at `~/.gitconfig-host` and is pulled in with an
  `[include]`, so name, email and your other settings stay in sync with the host.
- 1Password's SSH agent socket is forwarded to `~/.1password/agent.sock`, exported as
  `SSH_AUTH_SOCK`. It signs commits and authenticates pushes.

**No key material enters the container.** The SSH agent protocol has two meaningful
operations, "list public identities" and "sign this blob," and nothing that returns a
private key, a password, or any other vault item. So a bypassed session in here can
ask for signatures but cannot walk away with anything, and cannot reach the rest of
your 1Password vault even in principle. That is a property of the protocol, not a
setting you have to get right.

Only one thing has to be overridden after the include (git config is last-wins):
`gpg.ssh.program`, from 1Password's macOS-only `op-ssh-sign` to plain `ssh-keygen`.
`user.signingkey` is inherited from the host untouched, and it being a *literal*
public key rather than a path is exactly what routes signing through the agent: git
passes `-U` to `ssh-keygen` for literals, meaning "find the private half in the
agent." The container ends up configured almost identically to the host, which is the
tell that this is the arrangement the tooling expects.

The script also writes a container-local `allowed_signers` covering that key, since
the host's copy lives at a macOS path. Without it `git log --show-signature` reports
an unknown principal instead of a good signature.

### Requirements and failure modes

Socket forwarding needs Docker Desktop's **VirtioFS** backend. The older gRPC-FUSE
cannot forward unix sockets. 1Password must also be unlocked on the host when the
container is created, since listing identities goes through the app.

The mount deliberately omits `readonly`: connecting to a unix socket requires write
permission on the inode, and a read-only bind mount fails in a way that looks like a
forwarding problem rather than a permissions one. It also binds the single
`agent.sock` file rather than its parent directory, which holds ~68 other 1Password
IPC sockets, including the CLI integration, which are nowhere near as narrow.

If anything goes wrong the script disables `commit.gpgsign` and says why, so commits
still work unsigned rather than failing outright. It distinguishes an unreachable or
locked agent, an agent holding no keys, and an agent that does not hold the key your
config names. That last one usually means `~/.config/1Password/ssh/agent.toml` scopes
the agent to a vault the key isn't in. Check what the container can actually see with
`ssh-add -L`, which prints exactly what the agent will offer and nothing more.

### Fallback

If your Docker Desktop can't forward the socket, comment out the agent mount in
[devcontainer.json](devcontainer.json) and uncomment the key mount below it. That
copies one private key to `~/.ssh/git_key` at `0600` and signs with the file directly.
The script detects which mode it's in with no further configuration. It's the less
safe option, because the key is then readable inside the container.

## Limits worth knowing

Claude's own credentials sit in `~/.claude` inside the container, and a malicious
repo could read them. Use this for repos you trust, which for a personal project
means: it protects you from Claude's mistakes and from injected content in API
responses, not from a determined supply-chain attacker.

Signing is confined but not free of risk. Agent forwarding means the key cannot be
stolen, so a compromised session leaves nothing durable behind once the container
stops. What it does not prevent is misuse while the container runs: anything that
reaches the socket can sign arbitrary commits and authenticate to GitHub as you. It is
confinement in time, not in capability.

1Password's per-use approval prompt is the only real check on that, and it gets weaker
through a forwarded socket. The app identifies callers by peer credentials, which
through Docker's forwarding resolve to the proxy on the host rather than to the process
in the container. I haven't verified what the prompt renders in that case, but the
consequence is structural: container requests are indistinguishable from each other, so
approving and remembering grants broadly rather than to one caller. Turn off
remembering in 1Password's developer settings if you want a tap per commit.

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
