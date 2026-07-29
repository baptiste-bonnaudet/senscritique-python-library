FROM mcr.microsoft.com/devcontainers/python:3.13-bookworm

# Firewall tooling (iptables/ipset/dig/aggregate) plus basics for dev and probes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    iptables \
    ipset \
    iproute2 \
    dnsutils \
    aggregate \
    jq \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# uv, same tool as on the host.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ARG USERNAME=vscode

# Pre-create the volume mount points so the named volumes inherit vscode ownership
# on first mount (Docker copies ownership from the image path).
RUN mkdir -p /home/$USERNAME/.claude /home/$USERNAME/.cache/uv /commandhistory \
    && touch /commandhistory/.bash_history \
    && chown -R $USERNAME:$USERNAME /home/$USERNAME/.claude /home/$USERNAME/.cache /commandhistory

# Persist shell history in the mounted volume, and a shortcut for unattended runs.
RUN echo 'export PROMPT_COMMAND="history -a" HISTFILE=/commandhistory/.bash_history' >> /etc/bash.bashrc \
    && echo 'export HISTFILE=/commandhistory/.bash_history' >> /etc/zsh/zshrc \
    && echo 'alias yolo="claude --dangerously-skip-permissions"' >> /etc/bash.bashrc \
    && echo 'alias yolo="claude --dangerously-skip-permissions"' >> /etc/zsh/zshrc

# Egress firewall script. Deliberately NOT named init-firewall.sh: the claude-code
# devcontainer feature installs its own script under that name, and features run
# after this Dockerfile, so it would silently overwrite ours.
#
# Strip the image's blanket passwordless sudo and allow the vscode user to run ONLY
# this script as root; otherwise a permission-skipping Claude could just flush
# iptables and the firewall would be decorative. /usr/local/bin is root-owned and
# not writable by vscode, so the script behind the sudo rule cannot be swapped.
COPY project-firewall.sh /usr/local/bin/project-firewall.sh
RUN chmod 755 /usr/local/bin/project-firewall.sh \
    && chown root:root /usr/local/bin/project-firewall.sh \
    && rm -f /etc/sudoers.d/* \
    && echo "$USERNAME ALL=(root) NOPASSWD: /usr/local/bin/project-firewall.sh" > /etc/sudoers.d/project-firewall \
    && chmod 0440 /etc/sudoers.d/project-firewall
