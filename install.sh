#!/bin/bash
# Antigravity / Claude / Codex Skill Installer for infinity-ads-compliance-audit

set -e

SKILL_NAME="infinity-ads-compliance-audit"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   🚀 Skill Installer: $SKILL_NAME      ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Make executables
chmod +x "$SCRIPT_DIR/bin/infinity-ads-audit.js" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/scripts/run_audit.py" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/scripts/package_skill.py" 2>/dev/null || true

# Target directories to install
TARGETS=()

# 1. Antigravity / Gemini CLI
if [ -d "$HOME/.gemini/antigravity" ] || [ -d "$HOME/.gemini/config" ]; then
    TARGETS+=("$HOME/.gemini/antigravity/skills/$SKILL_NAME")
fi

# 2. Claude Code (if directory exists)
if [ -d "$HOME/.claude" ]; then
    TARGETS+=("$HOME/.claude/skills/$SKILL_NAME")
fi

# 3. OpenAI Codex — reads $CODEX_HOME/skills, which defaults to ~/.codex/skills
CODEX_SKILL_HOME="${CODEX_HOME:-$HOME/.codex}"
if [ -d "$CODEX_SKILL_HOME" ]; then
    TARGETS+=("$CODEX_SKILL_HOME/skills/$SKILL_NAME")
fi

# 4. Legacy/other agents that read ~/.agents/skills
if [ -d "$HOME/.agents" ]; then
    TARGETS+=("$HOME/.agents/skills/$SKILL_NAME")
fi

# Fallback if none found: default to Gemini / Antigravity
if [ ${#TARGETS[@]} -eq 0 ]; then
    TARGETS+=("$HOME/.gemini/antigravity/skills/$SKILL_NAME")
fi

echo "⏳ Installing skill files..."
for target in "${TARGETS[@]}"; do
    mkdir -p "$target"
    rsync -a --exclude='.git' --exclude='CLAUDE.md' --exclude='__pycache__' --exclude='*.pyc' --exclude='ads-audit-output' --exclude='node_modules' "$SCRIPT_DIR/" "$target/" 2>/dev/null || cp -R "$SCRIPT_DIR/"* "$target/"
    echo "   ✅ Installed to: $target"
done

echo ""
echo "🎉 Skill '$SKILL_NAME' installed successfully!"
echo "   You can now trigger the audit in Antigravity, Claude Code, or Codex."
echo ""
