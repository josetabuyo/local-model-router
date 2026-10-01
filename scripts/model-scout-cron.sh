#!/bin/bash
# Daily unattended run of /model-scout, triggered by launchd (see
# ~/Library/LaunchAgents/com.localmodels.model-scout.plist). Runs headless,
# with permission checks bypassed since there's no one to approve prompts.
set -euo pipefail

cd /Users/josetabuyo/Development/local-models

# caffeinate -s -i: Maintenance Sleep fires on battery AND on AC (audit notes
# 2026-09-27/28) and turns live probes into HTTP 000 artifacts. -s only holds
# on AC; on battery the probes may still be interrupted — plug the Mac in.
/usr/bin/caffeinate -s -i /Users/josetabuyo/.local/bin/claude -p "/model-scout" \
  --dangerously-skip-permissions
