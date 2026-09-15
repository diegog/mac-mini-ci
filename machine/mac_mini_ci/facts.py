"""Read-only facts for things pyinfra has no macOS support for.

pyinfra's server.Users/Groups read /etc/passwd, which does not contain Open Directory accounts;
launchd.LaunchdStatus only knows `launchctl list`; there is nothing for `defaults`, `pmset` or
`scutil`. Each fact here is one command whose output says whether a step is already done.

Facts fetched inside an `_if` guard run at execute time, before the operation's arguments apply:
they get neither the op's `_sudo`/`_env` nor config.ENV. Pass `_sudo=True`/`_sudo_user=` explicitly
and use absolute paths for anything outside sshd's default PATH.
"""

from __future__ import annotations

import shlex

from pyinfra.api import FactBase

from mac_mini_ci.paths import SOFTNET, TART


class Defaults(FactBase):
    """Value of `defaults read <domain> <key>` as a string, or None if unset.

    `current_host=True` reads the ByHost (per-machine) domain, as `defaults -currentHost` does.
    """

    def command(self, domain: str, key: str, current_host: bool = False) -> str:
        flag = "-currentHost " if current_host else ""
        return f"defaults {flag}read {shlex.quote(domain)} {shlex.quote(key)} 2>/dev/null || true"

    def process(self, output: list[str]):
        text = "\n".join(output).strip()
        return text or None


class DefaultsArray(FactBase):
    """A `defaults read` array as a list of strings (None if unset)."""

    def command(self, domain: str, key: str) -> str:
        return f"defaults read {shlex.quote(domain)} {shlex.quote(key)} 2>/dev/null || true"

    def process(self, output: list[str]):
        items = []
        for line in output:
            line = line.strip().rstrip(",")
            if line in ("(", ")", ""):
                continue
            items.append(line.strip('"'))
        return items or None


class ScutilPref(FactBase):
    """`scutil --get <HostName|LocalHostName|ComputerName>`, or None when not set."""

    def command(self, pref: str) -> str:
        return f"scutil --get {shlex.quote(pref)} 2>/dev/null || true"

    def process(self, output: list[str]):
        text = "\n".join(output).strip()
        return text or None


class PmsetCustom(FactBase):
    """`pmset -g custom` as {setting: value}. A Mac mini has one power source, so one block."""

    default = dict

    def command(self) -> str:
        return "pmset -g custom"

    def process(self, output: list[str]):
        settings = {}
        for line in output:
            parts = line.split()
            if len(parts) == 2 and not line.endswith(":"):
                settings[parts[0]] = parts[1]
        return settings


class LaunchdLoaded(FactBase):
    """True if `launchctl print system/<label>` succeeds (service is bootstrapped)."""

    def command(self, label: str) -> str:
        return f"launchctl print system/{shlex.quote(label)} >/dev/null 2>&1 && echo yes || echo no"

    def process(self, output: list[str]):
        return output[-1].strip() == "yes" if output else False


class DsclUserUid(FactBase):
    """UniqueID of an Open Directory user, or None if the user does not exist."""

    def command(self, user: str) -> str:
        return f"dscl . -read /Users/{shlex.quote(user)} UniqueID 2>/dev/null || true"

    def process(self, output: list[str]):
        for line in output:
            if line.startswith("UniqueID:"):
                return int(line.split(":", 1)[1].strip())
        return None


class SecureToken(FactBase):
    """True if `sysadminctl -secureTokenStatus <user>` reports ENABLED."""

    def command(self, user: str) -> str:
        return f"sysadminctl -secureTokenStatus {shlex.quote(user)} 2>&1 || true"

    def process(self, output: list[str]):
        return any("ENABLED" in line for line in output)


class FileVaultOn(FactBase):
    """True if FileVault is on."""

    def command(self) -> str:
        return "fdesetup status"

    def process(self, output: list[str]):
        return any("FileVault is On" in line for line in output)


class SoftwareUpdateScheduleOff(FactBase):
    """True only if `softwareupdate --schedule` says checking is turned off. Any other wording
    (a new macOS release, an error) counts as "not off", so the setter runs and asserts."""

    def command(self) -> str:
        return "softwareupdate --schedule 2>&1 || true"

    def process(self, output: list[str]):
        return "turned off" in " ".join(output).lower()


class DevToolsSecurity(FactBase):
    """True if developer mode is enabled (`DevToolsSecurity -status`)."""

    def command(self) -> str:
        return "DevToolsSecurity -status 2>&1 || true"

    def process(self, output: list[str]):
        return any("enabled" in line for line in output)


class SoftnetSuid(FactBase):
    """True if the softnet binary Homebrew's symlink points at is root-owned and setuid."""

    def command(self) -> str:
        return f"P=$(readlink -f {SOFTNET} 2>/dev/null) && stat -f '%Su %Sp' \"$P\" 2>/dev/null || true"

    def process(self, output: list[str]):
        if not output:
            return False
        owner, _, mode = output[-1].partition(" ")
        return owner == "root" and len(mode) > 3 and mode[3] == "s"


class TartImages(FactBase):
    """Names from `tart list -q` (local VMs and pulled OCI images; digest pulls list as name@sha256:…)."""

    default = list

    def requires_command(self) -> str:
        return TART  # `command -v /opt/homebrew/bin/tart` works without PATH

    def command(self) -> str:
        return f"{TART} list -q 2>/dev/null || true"

    def process(self, output: list[str]):
        return [line.strip() for line in output if line.strip()]
