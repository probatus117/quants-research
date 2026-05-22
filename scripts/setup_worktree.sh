#!/usr/bin/env bash
# scripts/setup_worktree.sh  KIK-745
#
#  worktree tests/fixtures/  sample  data/
# 
#
# Usage:
#   bash scripts/setup_worktree.sh KIK-NNN [short-desc]
#
# Example:
#   bash scripts/setup_worktree.sh KIK-748 add-feature
#
# :
#    PF  ~/stock-skills/data/portfolio.csv
#    sample fixture

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 KIK-NNN [short-desc]" >&2
    exit 1
fi

ISSUE="$1"
SHORT_DESC="${2:-task}"

#  Issue KIK-748 -> kik748
ISSUE_LOWER=$(echo "$ISSUE" | tr '[:upper:]' '[:lower:]' | tr -d '-')
BRANCH="feature/$(echo "$ISSUE" | tr '[:upper:]' '[:lower:]')-${SHORT_DESC}"
WORKTREE="${HOME}/stock-skills-${ISSUE_LOWER}"

# main repo path
MAIN_REPO="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -d "$WORKTREE" ]]; then
    echo "Error: worktree already exists at $WORKTREE" >&2
    exit 1
fi

echo "Creating worktree:"
echo "  branch:  $BRANCH"
echo "  path:    $WORKTREE"
git -C "$MAIN_REPO" worktree add -b "$BRANCH" "$WORKTREE" main

echo "Seeding sample fixtures (NOT personal PF):"
mkdir -p "$WORKTREE/data"
cp "$MAIN_REPO/tests/fixtures/sample_portfolio.csv" "$WORKTREE/data/portfolio.csv"
cp "$MAIN_REPO/tests/fixtures/sample_cash_balance.json" "$WORKTREE/data/cash_balance.json"
echo "   data/portfolio.csv      (from sample_portfolio.csv)"
echo "   data/cash_balance.json  (from sample_cash_balance.json)"

cat <<EOF

 Worktree ready: $WORKTREE
   cd $WORKTREE
   python3 -m pytest tests/ -q   #  unit tests pass without personal data

 :
    worktree 
    PF :
     export STOCK_SKILLS_DATA_DIR=$HOME/stock-skills/data
    PF cp  worktree
EOF
