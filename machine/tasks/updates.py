"""macOS never restarts itself for an update; security data (XProtect etc.) keeps flowing.

On macOS 26 and earlier this is `softwareupdate --schedule off` plus the com.apple.SoftwareUpdate
defaults. On macOS 27 both are silently ignored (verified on 27.0: the setter exits 0 and the getter
still says "turned on"; the plist edits take but softwareupdated no longer reads them — the policy
moved to the DDM store, which only System Settings or an MDM can write). There the setting is a
one-time GUI step; see the README. Background Security Improvements (26.1+) are GUI-only on every
version.
"""

from pyinfra import host
from pyinfra.facts.server import MacosVersion
from pyinfra.operations import server

from mac_mini_ci.facts import Defaults, SoftwareUpdateScheduleOff

SU = "/Library/Preferences/com.apple.SoftwareUpdate"
COMMERCE = "/Library/Preferences/com.apple.commerce"

major = int(host.get_fact(MacosVersion).split(".")[0])

if major >= 27:
    host.noop(
        "macOS 27+: automatic-update policy is not scriptable without MDM. Set it once in "
        "System Settings > General > Software Update > Automatic Updates: everything off except "
        "security responses (over Screen Sharing: `--data screen_sharing=true`)."
    )
else:
    # Setter plus read-back: an unrecognised wording must fail loudly, not leave checking on.
    server.shell(
        name="Software Update: no automatic checking",
        commands=[
            "softwareupdate --schedule off",
            "softwareupdate --schedule 2>&1 | grep -qi 'turned off'",
        ],
        _sudo=True,
        _if=lambda: not host.get_fact(SoftwareUpdateScheduleOff, _sudo=True),
    )

    KEYS = {
        "AutomaticallyInstallMacOSUpdates": False,
        "AutomaticDownload": False,
        "AutomaticallyInstallAppUpdates": False,
        "ConfigDataInstall": True,  # XProtect / MRT / Gatekeeper data
        "CriticalUpdateInstall": True,
    }
    for key, enabled in KEYS.items():
        server.shell(
            name=f"Software Update: {key} = {enabled}",
            commands=[f"defaults write {SU} {key} -bool {'true' if enabled else 'false'}"],
            _sudo=True,
            _if=lambda k=key, e=enabled: host.get_fact(Defaults, domain=SU, key=k, _sudo=True)
            != ("1" if e else "0"),
        )

    server.shell(
        name="App Store: no automatic app updates",
        commands=[f"defaults write {COMMERCE} AutoUpdate -bool false"],
        _sudo=True,
        _if=lambda: host.get_fact(Defaults, domain=COMMERCE, key="AutoUpdate", _sudo=True) != "0",
    )
