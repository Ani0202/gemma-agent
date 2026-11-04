#!/usr/bin/env bash
# One-time setup on the Oracle VM (Ubuntu, ARM). Run as your normal user from the unzipped kit:
#   bash setup_vm.sh
# Uses NO sudo unless a required package is missing AND passwordless sudo works; otherwise it
# prints the one command you need to run. Installs gcloud + kaggle in your home directory.
# Touches nothing outside ~/work/gemma, ~/.local, ~/google-cloud-sdk, ~/.venvs/gemma, ~/.config/gemma.
set -euo pipefail
KIT=$(cd "$(dirname "$0")" && pwd)
DEST=${DEST:-$HOME/work/gemma}
mkdir -p "$HOME/.local/bin"; export PATH="$HOME/.local/bin:$HOME/google-cloud-sdk/bin:$PATH"
echo "== system packages (check only) =="
missing=()
for pkg in jq tmux unzip git curl python3-venv; do dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg"); done
if [ ${#missing[@]} -gt 0 ]; then
  if sudo -n /usr/bin/true 2>/dev/null; then sudo apt-get install -y "${missing[@]}"
  else echo "NEED_SUDO: run this yourself, then re-run setup:  sudo apt-get install -y ${missing[*]}"; exit 10; fi
else echo "all present"; fi
echo "== gcloud (user-space) =="
if ! command -v gcloud >/dev/null; then
  arch=$(uname -m); case "$arch" in aarch64|arm64) f=google-cloud-cli-linux-arm.tar.gz;; *) f=google-cloud-cli-linux-x86_64.tar.gz;; esac
  curl -fsSL -o "/tmp/$f" "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/$f"
  tar -xzf "/tmp/$f" -C "$HOME" && rm -f "/tmp/$f"
  "$HOME/google-cloud-sdk/install.sh" --quiet --path-update false --usage-reporting false >/dev/null
  ln -sf "$HOME/google-cloud-sdk/bin/gcloud" "$HOME/.local/bin/gcloud"
fi
gcloud --version | head -1
echo "== kaggle CLI (venv) =="
[ -x "$HOME/.venvs/gemma/bin/kaggle" ] || { python3 -m venv "$HOME/.venvs/gemma" && "$HOME/.venvs/gemma/bin/pip" install -q --upgrade pip kaggle; }
ln -sf "$HOME/.venvs/gemma/bin/kaggle" "$HOME/.local/bin/kaggle"
echo "== repo =="
mkdir -p "$DEST"; cp -rn "$KIT"/. "$DEST"/; cd "$DEST"; chmod +x bin/* setup_vm.sh
[ -d .git ] || { git init -q -b main && git add -A && git commit -qm "kit: initial"; }
echo "== phone notifications (ntfy) =="
mkdir -p "$HOME/.config/gemma"; chmod 700 "$HOME/.config/gemma"
[ -f "$HOME/.config/gemma/ntfy.env" ] || { echo "NTFY_TOPIC=gemma-$(openssl rand -hex 12)" > "$HOME/.config/gemma/ntfy.env"; chmod 600 "$HOME/.config/gemma/ntfy.env"; }
source "$HOME/.config/gemma/ntfy.env"
mkdir -p "$HOME/.claude-gemma"
grep -q 'google-cloud-sdk/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$HOME/google-cloud-sdk/bin:$PATH"' >> "$HOME/.bashrc"
echo "== checks =="
for c in claude codex kaggle gcloud jq tmux; do printf '%-7s %s\n' "$c" "$(command -v $c || echo MISSING)"; done
uname -m; df -h ~ | tail -1; free -h | head -2
[ -n "${ANTHROPIC_API_KEY:-}" ] && echo "WARNING: ANTHROPIC_API_KEY is set; remove it so Claude Code uses your plan, not API billing."
echo "NTFY_TOPIC=$NTFY_TOPIC"
echo "SETUP_OK repo=$DEST"
