#!/usr/bin/env sh
# Installs the Cinema 4D skills from this repository for Claude Code and Codex.
#
# Copies every skill directory next to this script into the skills directory of
# each assistant found on this machine. Existing skills are left alone unless
# --force is passed, and a skill that is a symlink is never overwritten, because
# that would write through the link into its source repository.
#
# Usage:  ./install.sh [--force]

set -eu

source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
force=0
[ "${1:-}" = "--force" ] && force=1

skills=""
for dir in "$source_dir"/*/; do
    [ -f "$dir/SKILL.md" ] || continue
    skills="$skills $(basename "$dir")"
done
if [ -z "$skills" ]; then
    echo "No skill directories found next to $source_dir" >&2
    exit 1
fi

targets=""
[ -d "$HOME/.claude" ] && targets="$targets $HOME/.claude/skills"
[ -d "$HOME/.codex" ] && targets="$targets $HOME/.codex/skills"
if [ -z "$targets" ]; then
    echo "Neither ~/.claude nor ~/.codex was found. Install Claude Code or Codex first." >&2
    exit 1
fi

installed=0
skipped=0

for target in $targets; do
    mkdir -p "$target"
    echo
    echo "$target"

    for skill in $skills; do
        destination="$target/$skill"

        if [ -L "$destination" ]; then
            echo "  skip  $skill - linked to another location, leaving it untouched"
            skipped=$((skipped + 1))
            continue
        fi
        if [ -e "$destination" ]; then
            if [ "$force" -eq 0 ]; then
                echo "  skip  $skill - already installed (use --force to overwrite)"
                skipped=$((skipped + 1))
                continue
            fi
            rm -rf "$destination"
        fi

        cp -R "$source_dir/$skill" "$destination"
        find "$destination" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
        echo "  ok    $skill"
        installed=$((installed + 1))
    done
done

echo
echo "Installed $installed, skipped $skipped. Restart the assistant to pick up new skills."
