#!/bin/bash
# Default-deny egress firewall for the pysenscritique dev container.
# Adapted from anthropics/claude-code .devcontainer/init-firewall.sh.
#
# Everything outbound is blocked except:
#   - DNS, loopback, the host network (editor <-> container), outbound SSH (git)
#   - GitHub (IP ranges from api.github.com/meta)
#   - the domains listed in ALLOWED_DOMAINS below
#
# Domains are resolved to IPs once, when this runs. If a CDN rotates IPs and a
# host becomes unreachable mid-session, just re-run it:
#   sudo /usr/local/bin/init-firewall.sh
set -euo pipefail
IFS=$'\n\t'

ALLOWED_DOMAINS=(
    # --- Claude Code, per code.claude.com/docs/en/network-config ---
    "api.anthropic.com"        # API requests, feature flags, WebFetch safety check
    "claude.ai"                # account authentication
    "claude.com"               # sign-in redirect, pre-approved doc fetches
    "platform.claude.com"      # OAuth token exchange / refresh
    "code.claude.com"          # documentation lookups
    "downloads.claude.ai"      # plugin downloads, updater
    "storage.googleapis.com"   # plugin metadata, artifact uploads
    "mcp-proxy.anthropic.com"  # claude.ai MCP connectors
    "registry.npmjs.org"       # npm install / auto-update of the CLI
    # Optional operational telemetry. Listed so the calls fail fast rather than
    # stalling; drop these lines and set CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
    # in devcontainer.json if you would rather send nothing.
    "http-intake.logs.us5.datadoghq.com"
    "browser-intake-us5-datadoghq.com"

    # --- Python toolchain ---
    "pypi.org"
    "files.pythonhosted.org"

    # --- GitHub asset hosts not covered by the meta IP ranges ---
    "raw.githubusercontent.com"
    "objects.githubusercontent.com"

    # --- VS Code server, marketplace, CDN ---
    "update.code.visualstudio.com"
    "marketplace.visualstudio.com"
    "vscode.blob.core.windows.net"
    "main.vscode-cdn.net"
    # Extension VSIX downloads go to <publisher>.gallery.vsassets.io and
    # <publisher>.gallerycdn.vsassets.io. Those are wildcard DNS names: every
    # publisher prefix resolves through the same CNAME chain to the same shared
    # IPs, so resolving one name per pattern covers all publishers. Without these,
    # any extension not already installed on your host fails with EHOSTUNREACH.
    "marketplace.gallery.vsassets.io"
    "marketplace.gallerycdn.vsassets.io"

    # --- This project: SensCritique. Live probes are part of the workflow. ---
    "senscritique.com"
    "www.senscritique.com"
    "old.senscritique.com"
    "apollo.senscritique.com"
)

echo "Configuring egress firewall..."

# Preserve Docker's embedded DNS NAT rules before flushing everything.
DOCKER_DNS_RULES=$(iptables-save -t nat 2>/dev/null | grep '127\.0\.0\.11' || true)

iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

# -F clears rules but NOT the default policy. Re-running this script (or running
# it twice during container create) would otherwise leave OUTPUT at DROP with an
# empty allowlist, and the GitHub/DNS lookups below would fail. Reopen first;
# the policy goes back to DROP at the end, once the allowlist is populated.
iptables -P INPUT ACCEPT
iptables -P FORWARD ACCEPT
iptables -P OUTPUT ACCEPT

if [ -n "$DOCKER_DNS_RULES" ]; then
    while read -r rule; do
        # shellcheck disable=SC2086
        iptables -t nat $rule
    done <<<"$DOCKER_DNS_RULES"
fi

# DNS, loopback and outbound SSH (git over ssh) stay open.
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

ipset create allowed-domains hash:net

echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s --connect-timeout 10 https://api.github.com/meta || true)
if [ -n "$gh_ranges" ] && echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null 2>&1; then
    while read -r cidr; do
        ipset add allowed-domains "$cidr" 2>/dev/null || true
    done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | grep -v ':' | aggregate -q)
else
    echo "WARNING: could not fetch GitHub IP ranges; GitHub over HTTPS may be blocked" >&2
fi

failed_domains=()
for domain in "${ALLOWED_DOMAINS[@]}"; do
    ips=$(dig +short A "$domain" | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true)
    if [ -z "$ips" ]; then
        failed_domains+=("$domain")
        continue
    fi
    while read -r ip; do
        ipset add allowed-domains "$ip" 2>/dev/null || true
    done <<<"$ips"
done
if [ ${#failed_domains[@]} -gt 0 ]; then
    echo "WARNING: these domains did not resolve and will be blocked: ${failed_domains[*]}" >&2
fi

# Host network: keeps the editor <-> container channel working.
HOST_IP=$(ip route | grep default | cut -d" " -f3 || true)
if [ -n "$HOST_IP" ]; then
    HOST_NETWORK=$(echo "$HOST_IP" | sed 's/\.[0-9]*$/.0\/24/')
    iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
    iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT
fi

# Default deny, then allow established flows and the allowlist.
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT
# Reject rather than drop, so blocked calls fail fast and visibly.
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

echo "Verifying firewall..."
if curl -s --connect-timeout 5 https://example.com >/dev/null 2>&1; then
    echo "ERROR: verification failed: example.com is reachable (egress not blocked)" >&2
    exit 1
fi
if ! curl -s --connect-timeout 10 https://api.anthropic.com >/dev/null 2>&1; then
    echo "ERROR: verification failed: api.anthropic.com is NOT reachable" >&2
    exit 1
fi
echo "Firewall active: unlisted egress blocked, api.anthropic.com reachable."
