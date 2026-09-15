"""Never sleep, come back after power loss, no lock screen at the login window."""

from pyinfra import host
from pyinfra.operations import server

from mac_mini_ci.facts import Defaults, DevToolsSecurity, PmsetCustom

PMSET = {
    "sleep": "0",
    "disksleep": "0",
    "displaysleep": "0",
    "womp": "1",  # "Wake for network access"
    "powernap": "0",
}
for key, value in PMSET.items():
    server.shell(
        name=f"pmset: {key} {value}",
        commands=[f"pmset -a {key} {value}"],
        _sudo=True,
        _if=lambda k=key, v=value: host.get_fact(PmsetCustom).get(k) != v,
    )


def _no_power_recovery() -> bool:
    custom = host.get_fact(PmsetCustom)
    return custom.get("autorestartatconnect") != "1" and custom.get("autorestart") != "1"


# `autorestartatconnect` (macOS 26.5+, Mac mini 2024+) powers the Mac on whenever wall power
# appears, so a smart plug can recover a hung host. The setter is model-gated; if it is refused,
# fall back to the classic restart-after-power-loss. Whether setting one clears the other is not
# documented; the read-back prints both so the first run shows what happened.
server.shell(
    name="pmset: start up when power is connected (or after power failure)",
    commands=[
        "pmset -a autorestartatconnect 1 || pmset -a autorestart 1",
        "pmset -g custom | grep -E '^ *autorestart' || true",
    ],
    _sudo=True,
    _if=_no_power_recovery,
)

SCREENSAVER = "/Library/Preferences/com.apple.screensaver"
server.shell(
    name="Login window: no screensaver",
    commands=[f"defaults write {SCREENSAVER} loginWindowIdleTime -int 0"],
    _sudo=True,
    _if=lambda: host.get_fact(Defaults, domain=SCREENSAVER, key="loginWindowIdleTime", _sudo=True)
    != "0",
)

server.shell(
    name="Developer mode (DevToolsSecurity)",
    commands=["DevToolsSecurity --enable"],
    _sudo=True,
    _if=lambda: not host.get_fact(DevToolsSecurity),
)
