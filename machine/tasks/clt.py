"""Xcode Command Line Tools, headless: the placeholder file makes `softwareupdate -l` offer them.
Same sequence Homebrew's installer and GitHub's runner images use. Provides git and python3."""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.operations import server

from mac_mini_ci.paths import CLT_GIT

INSTALL = r"""
set -eu
placeholder=/tmp/.com.apple.dt.CommandLineTools.installondemand.in-progress
touch "$placeholder"
trap 'rm -f "$placeholder"' EXIT
label=$(softwareupdate -l 2>/dev/null \
  | grep -B 1 -E 'Command Line Tools' \
  | awk -F'*' '/^ *\*/ {print $2}' \
  | sed -e 's/^ *Label: //' -e 's/^ *//' \
  | sort -V | tail -n1)
[ -n "$label" ] || { echo "softwareupdate -l offered no Command Line Tools label"; exit 1; }
echo "installing: $label"
softwareupdate -i "$label"
xcode-select --switch /Library/Developer/CommandLineTools
test -x """ + CLT_GIT

server.shell(
    name="Xcode Command Line Tools",
    commands=[INSTALL],
    _sudo=True,
    _shell_executable="bash",
    _timeout=3600,
    _retries=3,  # Apple's catalog occasionally lags
    _retry_delay=60,
    _if=lambda: not host.get_fact(File, path=CLT_GIT),
)
