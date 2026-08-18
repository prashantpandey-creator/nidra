#!/usr/bin/env bash
# Nidra installer — Mac and Linux. Never asks for a password, touches nothing
# outside ~/.nidra-app and one line on your PATH.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP="$HOME/.nidra-app"
BIN="$HOME/.local/bin"

say() { printf "  %s\n" "$1"; }

echo
echo "Installing Nidra"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "  Nidra needs Python 3.9 or newer, and python3 was not found."
  echo "  Install it from python.org, then run this again."
  exit 1
fi
PYV="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
say "found python $PYV"

rm -rf "$APP"
mkdir -p "$APP" "$BIN"
cp -R "$HERE/runtime/nidra" "$APP/nidra"
say "copied Nidra to $APP"

cat > "$BIN/nidra" <<EOF
#!/usr/bin/env bash
exec python3 -c 'import sys; sys.path.insert(0, "$APP"); from nidra.cli import main; sys.exit(main())' "\$@"
EOF
chmod +x "$BIN/nidra"
say "created the 'nidra' command in $BIN"

if ! echo ":$PATH:" | grep -q ":$BIN:"; then
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    [ -f "$rc" ] || continue
    grep -q 'nidra installer' "$rc" 2>/dev/null && continue
    printf '\n# added by the nidra installer\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc"
    say "added $BIN to your PATH in $(basename "$rc")"
  done
  echo
  echo "  Open a NEW terminal, then run:  nidra demo"
else
  echo
  echo "  Done. Try it now:  nidra demo"
fi
echo
