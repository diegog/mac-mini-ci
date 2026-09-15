"""mac-release lane: one persistent GitHub Actions runner on the host, as `ci`, under launchd.

Registration needs a one-hour token, minted on the workstation from the GitHub App during prepare,
and only when the runner is not yet configured. `--disableupdate` pins the version: bump
runner_version/runner_sha256 in group data and rerun (GitHub stops queuing jobs to runners more
than 30 days behind).
"""

from pyinfra import host
from pyinfra.api import HiddenValue
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import files, server

from mac_mini_ci.facts import LaunchdLoaded
from mac_mini_ci.github_app import installation_token, registration_token

ci = host.data.ci_user
repo = host.data.github_repo
name = host.data.release_runner_name
version = host.data.runner_version
ROOT = f"/Users/{ci}/actions-runner"
TARBALL = f"/Users/{ci}/mac-mini-ci/runner/actions-runner-osx-arm64-{version}.tar.gz"  # cached by tasks/github_app.py
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
configured = all([repo, host.data.github_app_id, host.data.github_app_key])

if configured:
    # The runner names its own service actions.runner.<owner-repo>.<name>; keep the same label.
    label = f"actions.runner.{repo.replace('/', '-')}.{name}"
    plist = f"/Library/LaunchDaemons/{label}.plist"

    files.directory(name="runner root", path=ROOT, user=ci, group="staff", mode="700", _sudo=True)
    files.directory(
        name="runner logs", path=f"/Users/{ci}/Library/Logs/{label}", user=ci, group="staff", mode="700", _sudo=True
    )

    def _not_installed() -> bool:
        # The marker carries the version, so a bump in group data re-unpacks over the old files
        # (registration in .runner/.credentials is untouched, like the runner's own updater).
        marker = host.get_fact(Command, command=f"cat {ROOT}/.mac-mini-ci-version 2>/dev/null || true", _sudo=True) or ""
        return marker.strip() != version

    unpack = server.shell(
        name=f"runner {version}: unpack",
        commands=[
            f"tar -xzf {TARBALL} -C {ROOT}",
            f"cp {ROOT}/bin/runsvc.sh {ROOT}/runsvc.sh && chmod +x {ROOT}/runsvc.sh",
            f"printf '%s\n' '{version}' > {ROOT}/.mac-mini-ci-version",
        ],
        _sudo=True,
        _sudo_user=ci,
        _if=_not_installed,
    )

    # Registration: prepare-time fact, so the token is only minted when it will be used.
    needs_registration = not host.get_fact(File, path=f"{ROOT}/.runner", _sudo=True)
    token = ""
    if needs_registration:
        token = registration_token(
            repo,
            installation_token(host.data.github_app_id, host.data.github_app_installation_id, host.data.github_app_key),
        )
    server.shell(
        name=f"runner {name}: register with GitHub",
        commands=[
            f"cd {ROOT} && ./config.sh --unattended --replace --disableupdate"
            f" --url https://github.com/{repo} --name {name}"
            f" --labels {','.join(host.data.release_runner_labels)} --work _work",
            # config.sh snapshots PATH into .path for the service; make it the curated one.
            f"printf '%s\\n' '{PATH}' > {ROOT}/.path",
        ],
        _sudo=True,
        _sudo_user=ci,
        _env={"ACTIONS_RUNNER_INPUT_TOKEN": HiddenValue(token), "PATH": PATH},
        _if=lambda: needs_registration,
    )

    rendered = files.template(
        name=f"runner {name}: LaunchDaemon plist",
        src="templates/actions-runner.plist.j2",
        dest=plist,
        user="root",
        group="wheel",
        mode="644",
        _sudo=True,
        label=label,
        runner_root=ROOT,
    )
    server.shell(
        name=f"runner {name}: reload daemon",
        commands=[f"launchctl bootout system/{label} 2>/dev/null || true", f"launchctl bootstrap system {plist}"],
        _sudo=True,
        _if=lambda: rendered.is_complete() and rendered.did_change(),
    )
    server.shell(
        name=f"runner {name}: daemon loaded",
        commands=[f"launchctl bootstrap system {plist}"],
        _sudo=True,
        _if=lambda: not (rendered.is_complete() and rendered.did_change())
        and not host.get_fact(LaunchdLoaded, label=label, _sudo=True),
    )
    # A new runner build under a running daemon: restart it so the new listener is used.
    server.shell(
        name=f"runner {name}: restart after upgrade",
        commands=[f"launchctl kickstart -k system/{label}"],
        _sudo=True,
        _if=lambda: unpack.is_complete() and unpack.did_change()
        and not (rendered.is_complete() and rendered.did_change()),
    )
