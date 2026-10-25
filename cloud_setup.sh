#!/bin/bash
# One-shot: create a private GitHub repo, push this pipeline, and load every
# secret from your local .env into GitHub Actions Secrets.
#
# First time only:
#   1) brew install gh        # the GitHub CLI
#   2) gh auth login          # sign in (choose GitHub.com -> HTTPS -> browser)
# Then:
#   bash cloud_setup.sh
set -e
cd "$(dirname "$0")"

command -v gh >/dev/null || { echo "❌ Install the GitHub CLI first:  brew install gh"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "❌ Sign in first:  gh auth login"; exit 1; }

REPO="mabcos-pipeline"
echo "→ Creating private repo '$REPO' and pushing…"
if gh repo view "$REPO" >/dev/null 2>&1; then
  git remote get-url origin >/dev/null 2>&1 || git remote add origin "$(gh repo view "$REPO" --json sshUrl -q .sshUrl)"
  git push -u origin HEAD
else
  gh repo create "$REPO" --private --source=. --remote=origin --push
fi

echo "→ Loading secrets from .env…"
set -a; . ./.env; set +a
for k in GEMINI_API_KEY PEXELS_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID FB_PAGE_TOKEN FB_PAGE_ID AMAZON_ASSOC_TAG; do
  v="$(eval printf '%s' "\${$k}")"
  if [ -n "$v" ]; then gh secret set "$k" --body "$v" >/dev/null && echo "   ✓ $k"; else echo "   ⚠ $k is empty in .env"; fi
done

echo
echo "✅ Done. Your pipeline is in the cloud."
echo "   Run it now to test:   gh workflow run mabcos.yml"
echo "   Watch it:             gh run watch"
echo "   It will then post automatically every day (08:00 & 19:30 PKT)."
