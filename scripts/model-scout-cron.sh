#!/bin/bash
# Daily unattended run of /model-scout, triggered by launchd (see
# ~/Library/LaunchAgents/com.localmodels.model-scout.plist). Runs headless,
# with permission checks bypassed since there's no one to approve prompts.
set -euo pipefail

cd /Users/josetabuyo/Development/local-models

/Users/josetabuyo/.local/bin/claude -p "/model-scout" \
  --dangerously-skip-permissions
