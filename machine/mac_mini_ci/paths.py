"""Paths several tasks agree on. Absolute on purpose: facts evaluated inside `_if` guards run
without config.ENV, i.e. with sshd's default PATH, which has no /opt/homebrew/bin."""

CLT_GIT = "/Library/Developer/CommandLineTools/usr/bin/git"
BREW = "/opt/homebrew/bin/brew"
TART = "/opt/homebrew/bin/tart"
SOFTNET = "/opt/homebrew/bin/softnet"
