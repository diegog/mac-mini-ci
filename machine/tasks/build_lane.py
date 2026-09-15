"""mac-build lane: N LaunchDaemons, each keeping one Tart VM slot busy with one-job JIT runners."""

from pyinfra import host
from pyinfra.operations import files, server

from mac_mini_ci.facts import LaunchdLoaded

ci = host.data.ci_user
configured = all([host.data.github_repo, host.data.github_app_id, host.data.github_app_key])

if configured:
    for slot in range(1, int(host.data.build_slots) + 1):
        label = f"ci.mac-mini-ci.mac-build.slot{slot}"
        plist = f"/Library/LaunchDaemons/{label}.plist"

        rendered = files.template(
            name=f"mac-build slot {slot}: LaunchDaemon plist",
            src="templates/mac-build-slot.plist.j2",
            dest=plist,
            user="root",
            group="wheel",
            mode="644",
            _sudo=True,
            label=label,
            slot=slot,
        )

        # A changed plist must be booted out and back in; a running job in that slot dies with
        # it, which is acceptable for a deploy. An unchanged, unloaded plist just gets loaded.
        server.shell(
            name=f"mac-build slot {slot}: reload daemon",
            commands=[
                f"launchctl bootout system/{label} 2>/dev/null || true",
                f"launchctl bootstrap system {plist}",
            ],
            _sudo=True,
            _if=lambda r=rendered: r.is_complete() and r.did_change(),
        )
        server.shell(
            name=f"mac-build slot {slot}: daemon loaded",
            commands=[f"launchctl bootstrap system {plist}"],
            _sudo=True,
            _if=lambda r=rendered, lb=label: not (r.is_complete() and r.did_change())
            and not host.get_fact(LaunchdLoaded, label=lb, _sudo=True),
        )
