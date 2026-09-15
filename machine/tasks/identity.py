"""Hostname, time zone, NTP. `systemsetup` needs root; only its Remote Login/Apple Events setters need Full Disk Access."""

import shlex

from pyinfra import host
from pyinfra.facts.server import Command
from pyinfra.operations import server

from mac_mini_ci.facts import ScutilPref

name = host.data.machine_name
tz = host.data.timezone
ntp = host.data.ntp_server

for pref in ("HostName", "LocalHostName", "ComputerName"):
    server.shell(
        name=f"Hostname: {pref} = {name}",
        commands=[f"scutil --set {pref} {shlex.quote(name)}"],
        _sudo=True,
        _if=lambda p=pref: host.get_fact(ScutilPref, pref=p) != name,
    )


def _systemsetup(getter: str) -> str:
    # Command facts return the output as one string (None when empty).
    return (host.get_fact(Command, command=f"systemsetup {getter} 2>/dev/null || true", _sudo=True) or "").strip()


server.shell(
    name=f"Time zone: {tz}",
    commands=[f"systemsetup -settimezone {shlex.quote(tz)}"],
    _sudo=True,
    _if=lambda: _systemsetup("-gettimezone") != f"Time Zone: {tz}",
)
server.shell(
    name=f"NTP server: {ntp}",
    commands=[f"systemsetup -setnetworktimeserver {shlex.quote(ntp)}"],
    _sudo=True,
    _if=lambda: _systemsetup("-getnetworktimeserver") != f"Network Time Server: {ntp}",
)
server.shell(
    name="NTP: on",
    commands=["systemsetup -setusingnetworktime on"],
    _sudo=True,
    _if=lambda: _systemsetup("-getusingnetworktime") != "Network Time: On",
)
