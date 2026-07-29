# VS Code Dev Containers — Cheat Sheet

A dev container is a Docker container that VS Code treats as the machine your project
lives on. The mental model: **your editor UI stays on the host, everything else moves
into the container**. Terminal, language servers, linters, debuggers, extensions, and
`claude` all run inside; your repo is bind-mounted in, so file edits show up on the host
instantly. It is defined by `.devcontainer/devcontainer.json`, committed to the repo, so
anyone who opens it gets a byte-identical environment. This is also why it works as a
security boundary: a process in the container can reach the mounted repo and whatever the
network policy allows, and nothing else on your machine.

## Daily commands

Everything is in the Command Palette (`Cmd+Shift+P`), all prefixed `Dev Containers:`.

| Command | When |
| --- | --- |
| **Reopen in Container** | Open the current folder in its container. The main one. |
| **Reopen Folder Locally** | Come back out to the host. |
| **Rebuild Container** | You changed `devcontainer.json` or the Dockerfile. |
| **Rebuild Without Cache** | Rebuild is misbehaving, or you want fresh base layers. |
| **Show Container Log** | A build or `postCreateCommand` failed and you need the output. |
| **Attach to Running Container** | Get into a container you did not start from VS Code. |
| **Clean Up Dev Containers** | Reclaim disk from stale containers and volumes. |

The bottom-left green corner shows the current container; click it for the same menu.

## Lifecycle hooks, in execution order

The single most useful thing to internalise, because putting a command in the wrong hook
is the most common source of "why did that not run".

| Hook | Runs | Use for |
| --- | --- | --- |
| `initializeCommand` | On the **host**, before the container exists | Host-side prep. Rare. |
| `onCreateCommand` | Once, at creation, before the repo is guaranteed final | Base setup. |
| `updateContentCommand` | At creation and on prebuild content updates | Fetching content. |
| `postCreateCommand` | Once, after creation, repo present | `npm install`, `make install`. |
| `postStartCommand` | **Every** container start | Anything not persisted, e.g. firewall rules. |
| `postAttachCommand` | Every time an editor attaches | Per-session niceties. |

Rule of thumb: if it survives a restart (installed packages), use `postCreate`. If it does
not (iptables rules live in the network namespace), use `postStart`.

## Minimal config

```jsonc
{
  "name": "my-project",
  "image": "mcr.microsoft.com/devcontainers/python:3.13-bookworm",
  // or: "build": { "dockerfile": "Dockerfile" }
  "features": {
    "ghcr.io/devcontainers/features/node:1": {}
  },
  "remoteUser": "vscode",
  "postCreateCommand": "make install",
  "customizations": {
    "vscode": {
      "extensions": ["charliermarsh.ruff"],
      "settings": { "terminal.integrated.defaultProfile.linux": "zsh" }
    }
  }
}
```

`devcontainer.json` is JSONC: comments and trailing commas are legal, despite the `.json`
extension.

## Persisting things

The workspace is bind-mounted and lives on the host. **Everything else in the container is
discarded on rebuild**, including your home directory. Use named volumes for anything you
want to keep, such as credentials, shell history, and package caches.

```jsonc
"mounts": [
  // named volume: survives rebuilds, invisible to the host
  "source=myproj-config-${devcontainerId},target=/home/vscode/.config,type=volume",
  // bind mount: a real host path, read-only
  "source=${localEnv:HOME}/.claude/skills,target=/home/vscode/.claude/skills,type=bind,readonly"
]
```

Useful variables: `${devcontainerId}` (stable per container config, so volumes are
per-project), `${localEnv:VAR}` (host env var), `${localWorkspaceFolder}` and
`${containerWorkspaceFolder}`.

## Features

Features are composable install scripts, so you avoid hand-rolling Dockerfile steps.
Browse them at [containers.dev/features](https://containers.dev/features).

```jsonc
"features": {
  "ghcr.io/devcontainers/features/node:1": { "version": "22" },
  "ghcr.io/devcontainers/features/docker-in-docker:2": {},
  "ghcr.io/anthropics/devcontainer-features/claude-code:1.0": {}
}
```

Features run **after** your Dockerfile, so a feature can overwrite files your Dockerfile
wrote. The `:1` style suffix pins the feature, not the tool it installs.

## CLI, for scripting and CI

```bash
npm install -g @devcontainers/cli

devcontainer up --workspace-folder .              # build and start
devcontainer up --workspace-folder . --remove-existing-container   # force clean rebuild
devcontainer exec --workspace-folder . make check # run a command inside
```

Invaluable for testing a `devcontainer.json` without the editor in the loop, and the only
way to use dev containers from CI.

## Gotchas

**Rebuild vs restart.** Editing `devcontainer.json` does nothing until you rebuild. VS Code
usually prompts, but not always. If a change seems ignored, rebuild.

**Features overwrite Dockerfile output.** They run afterwards. If both write the same path,
the feature wins, silently. Name your files distinctly.

**Home directory is not the workspace.** Anything written to `~` vanishes on rebuild unless
it is a volume. Bind mounts of host dotfiles are read at container start, not synced live.

**Bind mount performance on macOS and Windows.** File I/O across the VM boundary is much
slower than native. Keep `node_modules`, `.venv`, and build caches in named volumes or
container-local paths, not in the bind-mounted workspace. On Linux, bind mounts are native
speed and this does not apply.

**Language-server config points at the host by default.** If your interpreter or toolchain
lives outside the workspace (a venv in `~`), set the path explicitly in
`customizations.vscode.settings` or the extension will not find it.

**Ports are not automatically public.** Use `forwardPorts` for predictable forwarding.
Auto-forwarding only catches processes VS Code notices.

**`remoteUser` matters.** Running as root means files created in the workspace are
root-owned on Linux hosts, and `claude --dangerously-skip-permissions` refuses to launch
as root. Set a non-root user.

**Git credentials.** VS Code forwards your host git credential helper and SSH agent
automatically. Convenient, but it means the container can act as you in git. Do not mount
`~/.ssh` directly.

**Extensions must be reinstalled per container.** Extensions listed under
`customizations.vscode.extensions` install automatically; anything you added manually to
your host VS Code will not be there.

**Extensions install from two different sources.** If an extension is already installed on
your host, VS Code copies the VSIX across; if not, the container downloads it from
`<publisher>.gallery.vsassets.io` and `<publisher>.gallerycdn.vsassets.io`. Behind an egress
firewall, allowlisting only `marketplace.visualstudio.com` silently breaks the second case,
so extensions you happen to have locally appear to work while the rest fail with
`EHOSTUNREACH`. Those are wildcard DNS names sharing one IP set, so one entry per pattern
covers every publisher. Extension install errors land in
`~/.vscode-server/data/logs/*/remoteagent.log`, not the container build log.

## Honest limits

A dev container is a Docker container, not a VM or a sandbox with a hard security promise.
It shares the host kernel. It protects you well from mistakes and from a project's build
scripts touching things outside the repo. It is not a defence against a determined
attacker with a kernel exploit, and by default it does not restrict outbound network
traffic at all (add a firewall for that). Anything you mount in is reachable, including
secrets, so mount narrowly and read-only.

Editors without dev container support (plain Vim, Emacs, Zed at time of writing) are not
part of this workflow. Supported: VS Code, GitHub Codespaces, Cursor, JetBrains IDEs.

## This repo

See [README.md](README.md). Short version: **Reopen in Container**, then `yolo` in the
terminal for a Claude session with permission prompts disabled inside the sandbox.

## One-liner

A committed `devcontainer.json` that turns a Docker container into your project's
development machine, so the toolchain is identical for everyone and everything except
your editor UI and your repo stays inside the box.
