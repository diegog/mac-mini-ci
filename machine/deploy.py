"""Host baseline for the Mac mini. Run from this directory: see README.md."""

from pyinfra import config, host, local
from pyinfra.facts.files import File
from pyinfra.operations import server

from mac_mini_ci.state import REBOOT_MARKER, reboot_triggers

config.REQUIRE_PYINFRA_VERSION = "~=3.10"

# Non-interactive SSH shells and launchd get no Homebrew PATH. Literal on purpose: since pyinfra
# 3.8 `_env` values are quoted, so "$PATH" would not expand. Applies to operations and to facts
# fetched inside them; facts fetched from an `_if` guard run before the op's arguments apply and
# get no PATH at all (hence the absolute paths in mac_mini_ci/paths.py).
config.ENV = {
    "PATH": "/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
    "HOMEBREW_NO_AUTO_UPDATE": "1",
    "HOMEBREW_NO_ANALYTICS": "1",
    "HOMEBREW_NO_ENV_HINTS": "1",
}

local.include("tasks/sanity.py")
local.include("tasks/access.py")
local.include("tasks/identity.py")
local.include("tasks/power.py")
local.include("tasks/updates.py")
local.include("tasks/network.py")
local.include("tasks/ci_user.py")

# The reboot comes before the long, failure-prone installs, and the need for it is recorded on
# the host: if a run dies later, the next run finds the triggers already satisfied and would
# otherwise never reboot.
server.shell(
    name="Reboot pending: mark",
    commands=[f"touch {REBOOT_MARKER}"],
    _sudo=True,
    _if=lambda: any(op.is_complete() and op.did_change() for op in reboot_triggers[host.name]),
)

reboot = server.reboot(
    name="Reboot (Local Network privacy and auto-login changes need it)",
    delay=20,
    reboot_timeout=900,
    _sudo=True,
    _if=lambda: bool(host.get_fact(File, path=REBOOT_MARKER, _sudo=True)),
)

# After the reboot `ci` should own the console; checked here so a wrong kcpassword is loud.
server.shell(
    name=f"Console session belongs to {host.data.ci_user}",
    commands=[f'[ "$(stat -f %Su /dev/console)" = {host.data.ci_user} ]'],
    _retries=18,  # the GUI login lands a while after sshd is back
    _retry_delay=10,
    _if=lambda: reboot.is_complete() and reboot.did_change(),
)

# Cleared only after the console check passed, so a failed check retries the reboot next run.
server.shell(
    name="Reboot pending: clear",
    commands=[f"rm -f {REBOOT_MARKER}"],
    _sudo=True,
    _if=lambda: reboot.is_complete() and reboot.did_change(),
)

local.include("tasks/clt.py")
local.include("tasks/homebrew.py")
local.include("tasks/tart.py")

# Runner workers; no-ops until MAC_MINI_GITHUB_* are set.
local.include("tasks/runners.py")
