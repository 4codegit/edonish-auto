#!/bin/bash
# Script to create GitHub release for v3.18.7

GITHUB_TOKEN="${1:-$GITHUB_TOKEN}"
REPO="4codegit/edonish-auto"
TAG="v3.18.7"

if [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: GITHUB_TOKEN required"
    echo "Usage: ./create_release.sh <token>"
    exit 1
fi

curl -s -H "Authorization: token $GITHUB_TOKEN" \
     -H "Accept: application/vnd.github.v3+json" \
     -X POST "https://api.github.com/repos/$REPO/releases" \
     -d '{
       "tag_name": "'$TAG'",
       "name": "Release '$TAG'",
       "body": "## What was fixed in v3.18.7\n\n### 🐛 Bug Fixes:\n- Fixed 409 Conflict errors when updating grades\n- Fixed NameError in error handlers\n- UI freeze fixed on large journal loading\n\n### ✨ Improvements:\n- Enhanced user info dialog\n- Auto-save grades on input\n- Show only numeric grades (no fractions)\n- Detailed logging for debugging\n\n### Full changelog:\n- v3.18.7: Fixed grade saving, improved user info display\n- v3.18.6: Add detailed logging for grade operations\n- v3.18.5: Auto-save grades on input\n- v3.18.4: Show only numeric grades\n- v3.18.3: Fixed UI freeze\n- v3.18.2: Fixed NameError\n- v3.18.1: UI fixes",
       "prerelease": false,
       "draft": false
     }' | jq .

echo ""
echo "Release created at: https://github.com/$REPO/releases/tag/$TAG"
