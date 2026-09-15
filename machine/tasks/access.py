"""SSH stays on, key-only, admin only; Screen Sharing is off unless asked for."""

from pyinfra import host
from pyinfra.operations import files, server

from mac_mini_ci.facts import LaunchdLoaded

SSHD = "com.openssh.sshd"
SSHD_PLIST = "/System/Library/LaunchDaemons/ssh.plist"
VNC = "com.apple.screensharing"
VNC_PLIST = "/System/Library/LaunchDaemons/com.apple.screensharing.plist"
DROPIN = "/etc/ssh/sshd_config.d/010-hardening.conf"

files.template(
    name="sshd: key-only login for the admin (drop-in)",
    src="templates/sshd-hardening.conf.j2",
    dest=DROPIN,
    user="root",
    group="wheel",
    mode="644",
    _sudo=True,
)

# sshd is spawned per connection, so the drop-in applies to the next login; no restart needed.
# If a future macOS rejects a keyword, every new connection would fail: move the file aside
# rather than leave a headless, VNC-off host unreachable. Always runs (it is an assertion).
server.shell(
    name="sshd: validate configuration (roll the drop-in back if rejected)",
    commands=[
        f"sshd -t || {{ mv {DROPIN} /var/tmp/010-hardening.conf.rejected; "
        "echo 'sshd rejected the drop-in; moved aside'; exit 1; }",
        f"sshd -T -C user={host.data.admin_user},host=localhost,addr=127.0.0.1"
        " | grep -qx 'passwordauthentication no'",
    ],
    _sudo=True,
)

server.shell(
    name="Remote Login: enabled",
    commands=[
        f"launchctl enable system/{SSHD}",
        f"launchctl bootstrap system {SSHD_PLIST} 2>/dev/null || true",
    ],
    _sudo=True,
    _if=lambda: not host.get_fact(LaunchdLoaded, label=SSHD, _sudo=True),
)

if host.data.screen_sharing:
    # Reach it through `ssh -L 5900:localhost:5900 infra@<host>`; launchd listens on all interfaces.
    server.shell(
        name="Screen Sharing: enabled (temporary)",
        commands=[
            f"launchctl enable system/{VNC}",
            f"launchctl bootstrap system {VNC_PLIST} 2>/dev/null || true",
        ],
        _sudo=True,
        _if=lambda: not host.get_fact(LaunchdLoaded, label=VNC, _sudo=True),
    )
else:
    server.shell(
        name="Screen Sharing: disabled",
        commands=[
            f"launchctl bootout system/{VNC} 2>/dev/null || true",
            f"launchctl disable system/{VNC}",
        ],
        _sudo=True,
        _if=lambda: host.get_fact(LaunchdLoaded, label=VNC, _sudo=True),
    )
