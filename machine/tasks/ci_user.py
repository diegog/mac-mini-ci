"""The `ci` account: standard user, auto-login, no first-login Setup Assistant, no screensaver.

Everything a job can touch runs as `ci`. Auto-login gives it the GUI session and unlocked login
keychain that Virtualization.framework (Tart) needs on macOS 15.2+; FileVault must stay off.
No secure token: FileVault is off and OS updates are `infra`'s job, so nothing needs one, and
skipping it keeps `infra`'s password off sysadminctl's argv.

Secrets: `ci`'s password travels in the environment (masked in pyinfra output) and is on the argv
of sysadminctl/dscl while those run; pyinfra's askpass likewise puts `infra`'s sudo password on
argv for every sudo'd command. macOS lets local users read other users' argv, so do not deploy
while untrusted work runs as `ci`.
"""

import hashlib
import io
import shlex

from pyinfra import host
from pyinfra.api import HiddenValue
from pyinfra.facts.files import Directory, Sha1File
from pyinfra.operations import files, server

from mac_mini_ci.facts import Defaults, DsclUserUid
from mac_mini_ci.kcpassword import encode
from mac_mini_ci.state import reboot_triggers

ci = host.data.ci_user
admin = host.data.admin_user
ci_pw = host.data.ci_password
LOGINWINDOW = "/Library/Preferences/com.apple.loginwindow"
TMP = f"/Users/{admin}/.pyinfra-tmp"

# sysadminctl exits 0 even when it fails and reports on stderr, so verify the record afterwards.
server.shell(
    name=f"User {ci}: create (standard user)",
    commands=[
        f"sysadminctl -addUser {ci} -fullName {shlex.quote(host.data.ci_full_name)}"
        f' -password "$CI_PW" -home /Users/{ci} 2>&1',
        f"dscl . -read /Users/{ci} UniqueID >/dev/null",
    ],
    _sudo=True,
    _env={"CI_PW": HiddenValue(ci_pw or "")},
    _if=lambda: host.get_fact(DsclUserUid, user=ci) is None,
)

# macOS 27's sysadminctl leaves the home folder to first login; create it now from the template.
server.shell(
    name=f"User {ci}: home directory",
    commands=[f"createhomedir -c -u {ci} >/dev/null", f"test -d /Users/{ci}"],
    _sudo=True,
    _if=lambda: not host.get_fact(Directory, path=f"/Users/{ci}", _sudo=True),
)

# A user created with sysadminctl gets the per-user Setup Assistant on first GUI login; on a
# headless box nobody can click through it. Apple's own opt-out file, consulted on every login.
files.file(
    name=f"User {ci}: no first-login Setup Assistant (~/.skipbuddy)",
    path=f"/Users/{ci}/.skipbuddy",
    user=ci,
    group="staff",
    mode="644",
    create_remote_dir=False,  # fail loudly if the home folder does not exist
    _sudo=True,
)

blob = encode(ci_pw or "")


def _kcpassword_stale() -> bool:
    return host.get_fact(Sha1File, path="/etc/kcpassword", _sudo=True) != hashlib.sha1(blob).hexdigest()


# Only when /etc/kcpassword is about to change: a wrong password here would leave the host at the
# login window after the reboot, with no GUI session for Tart.
server.shell(
    name=f"User {ci}: password matches what auto-login will store",
    commands=[f'dscl /Search -authonly {ci} "$CI_PW"'],
    _env={"CI_PW": HiddenValue(ci_pw or "")},
    _if=_kcpassword_stale,
)

# 0700 staging dir so the upload never sits world-readable in /tmp before its chmod.
files.directory(name="pyinfra staging dir (0700)", path=TMP, mode="700")

kcpassword = files.put(
    name="Auto-login: /etc/kcpassword",
    src=io.BytesIO(blob),
    dest="/etc/kcpassword",
    user="root",
    group="wheel",
    mode="600",
    _sudo=True,
    _temp_dir=TMP,
)
reboot_triggers[host.name].append(kcpassword)

autologin = server.shell(
    name=f"Auto-login: loginwindow autoLoginUser = {ci}",
    commands=[
        f"defaults write {LOGINWINDOW} autoLoginUser -string {ci}",
        f"defaults write {LOGINWINDOW} autoLoginUserScreenLocked -bool false",
    ],
    _sudo=True,
    _if=lambda: host.get_fact(Defaults, domain=LOGINWINDOW, key="autoLoginUser", _sudo=True) != ci,
)
reboot_triggers[host.name].append(autologin)

# Per-user settings, written as `ci` (sudo -H -u ci) so they land in /Users/ci/Library.
server.shell(
    name=f"User {ci}: no screensaver",
    commands=["defaults -currentHost write com.apple.screensaver idleTime -int 0"],
    _sudo=True,
    _sudo_user=ci,
    _if=lambda: host.get_fact(
        Defaults, domain="com.apple.screensaver", key="idleTime", current_host=True,
        _sudo=True, _sudo_user=ci,
    )
    != "0",
)
server.shell(
    name=f"User {ci}: no App Nap",
    commands=["defaults write NSGlobalDomain NSAppSleepDisabled -bool true"],
    _sudo=True,
    _sudo_user=ci,
    _if=lambda: host.get_fact(
        Defaults, domain="NSGlobalDomain", key="NSAppSleepDisabled", _sudo=True, _sudo_user=ci
    )
    != "1",
)
