#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
target="${1:-$HOME/.local/bin}"

mkdir -p "$target"
ln -sf "$repo/bin/waybar-calendar" "$target/waybar-calendar"
echo "linked $target/waybar-calendar -> $repo/bin/waybar-calendar"

case ":$PATH:" in
    *":$target:"*) ;;
    *) echo "warning: $target is not on PATH" ;;
esac
