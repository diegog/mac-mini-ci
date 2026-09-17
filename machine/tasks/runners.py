"""GitHub Actions workers: two Tart VM slots serving the mac-build and mac-release lanes.

Skipped (with a notice) when no GitHub App is configured. Also retires the earlier layout
(per-lane slot daemons and a persistent host runner) if it is still present.
"""

from pyinfra import host
from pyinfra.operations import files, python, server

from pyinfra.facts.files import File

from mac_mini_ci.facts import LaunchdLoaded
from mac_mini_ci.github_app import installation_token, list_runners, delete_runner

ci = host.data.ci_user
HOME = f"/Users/{ci}"
BASE = f"{HOME}/mac-mini-ci"
BIN = f"{BASE}/bin"
CACHE = f"{BASE}/runner"
SIGNING = f"{BASE}/signing"
LOGS = f"{HOME}/Library/Logs/mac-mini-ci"
KEY = f"{HOME}/.config/mac-mini-ci/github-app.pem"
version = host.data.runner_version
TARBALL = f"actions-runner-osx-arm64-{version}.tar.gz"
TMP = f"/Users/{host.data.admin_user}/.pyinfra-tmp"

configured = all(
    [host.data.github_repo, host.data.github_app_id, host.data.github_app_installation_id, host.data.github_app_key]
)

if not configured:
    host.noop("GitHub App not configured (MAC_MINI_GITHUB_*): skipping the runner workers")
else:
    for path in (f"{HOME}/.config", f"{HOME}/.config/mac-mini-ci", BASE, BIN, CACHE, SIGNING, f"{BASE}/run", LOGS):
        files.directory(name=f"dir {path}", path=path, user=ci, group="staff", mode="700", _sudo=True)

    # The App key: only `ci` reads it, only through github-app-token.
    key = files.put(
        name="GitHub App private key",
        src=host.data.github_app_key,
        dest=KEY,
        user=ci,
        group="staff",
        mode="600",
        _sudo=True,
        _temp_dir=TMP,
    )

    # The pinned runner build, cached once and shared read-only into every VM (the image's
    # bundled copy ages out: GitHub refuses runners more than ~30 days behind).
    files.download(
        name=f"runner {version}: cache tarball",
        src=f"https://github.com/actions/runner/releases/download/v{version}/{TARBALL}",
        dest=f"{CACHE}/{TARBALL}",
        sha256sum=host.data.runner_sha256,
        mode="644",
        _sudo=True,
        _sudo_user=ci,
    )

    # Signing material for release VMs, mounted read-only only into those. Optional until you
    # have it; the password for the .p12 lives in a GitHub environment secret, never here.
    for data_key, filename in (("signing_p12", "developer-id.p12"), ("notary_key", "AuthKey.p8")):
        src = getattr(host.data, data_key, None)
        if src:
            files.put(
                name=f"signing: {filename}",
                src=src,
                dest=f"{SIGNING}/{filename}",
                user=ci,
                group="staff",
                mode="600",
                _sudo=True,
                _temp_dir=TMP,
            )

    env = files.template(
        name="runners.env",
        src="templates/runners.env.j2",
        dest=f"{BASE}/runners.env",
        user=ci,
        group="staff",
        mode="600",
        _sudo=True,
    )
    scripts = [
        files.put(name=f"script {name}", src=f"files/{name}", dest=f"{BIN}/{name}", user=ci, group="staff", mode="755", _sudo=True)
        for name in ("github-app-token", "mac-worker")
    ]

    # Prove the key -> JWT -> installation token chain from the host, as ci, when inputs changed.
    server.shell(
        name="GitHub App: token helper works as ci",
        commands=[f"{BIN}/github-app-token >/dev/null"],
        _sudo=True,
        _sudo_user=ci,
        _if=lambda: any(op.is_complete() and op.did_change() for op in (key, env, *scripts)),
    )

    # --- retire the earlier layout -------------------------------------------------------------
    legacy_labels = [f"ci.mac-mini-ci.mac-build.slot{n}" for n in (1, 2)] + [
        f"actions.runner.{host.data.github_repo.replace('/', '-')}.mac-release"
    ]
    for label in legacy_labels:
        server.shell(
            name=f"retire {label}",
            commands=[f"launchctl bootout system/{label} 2>/dev/null || true", f"rm -f /Library/LaunchDaemons/{label}.plist"],
            _sudo=True,
            _if=lambda lb=label: host.get_fact(LaunchdLoaded, label=lb, _sudo=True)
            or bool(host.get_fact(File, path=f"/Library/LaunchDaemons/{lb}.plist", _sudo=True)),
        )
    for path in (f"{BIN}/mac-build-slot", f"{BASE}/mac-build.env"):
        files.file(name=f"retire {path}", path=path, present=False, _sudo=True)
    files.directory(name="retire host runner dir", path=f"{HOME}/actions-runner", present=False, _sudo=True)
    files.directory(name="retire slot logs", path=f"{HOME}/Library/Logs/mac-build", present=False, _sudo=True)

    # On GitHub (from the workstation, at execute time so --dry has no side effects): drop the old
    # persistent host runner and any offline one-job registrations left by retired daemons.
    def _sweep_registrations() -> None:
        token = installation_token(
            host.data.github_app_id, host.data.github_app_installation_id, host.data.github_app_key
        )
        for runner in list_runners(host.data.github_repo, token):
            if runner["name"] == "mac-release" or (
                runner["name"].startswith("mac-") and runner["status"] == "offline" and not runner["busy"]
            ):
                delete_runner(host.data.github_repo, token, runner["id"])
                print(f"    deregistered {runner['name']} (id {runner['id']})")

    python.call(name="GitHub: sweep stale runner registrations", function=_sweep_registrations)

    # Worker logs: rotated by newsyslog (already scheduled by launchd), which HUPs the worker to
    # reopen its file. Without a pid file newsyslog would HUP syslogd instead.
    files.template(
        name="newsyslog: rotate worker logs",
        src="templates/newsyslog.conf.j2",
        dest="/etc/newsyslog.d/mac-mini-ci.conf",
        user="root",
        group="wheel",
        mode="644",
        _sudo=True,
        workers=range(1, int(host.data.workers) + 1),
    )

    # --- workers ------------------------------------------------------------------------------
    for worker in range(1, int(host.data.workers) + 1):
        label = f"ci.mac-mini-ci.worker{worker}"
        plist = f"/Library/LaunchDaemons/{label}.plist"
        rendered = files.template(
            name=f"worker {worker}: LaunchDaemon plist",
            src="templates/mac-worker.plist.j2",
            dest=plist,
            user="root",
            group="wheel",
            mode="644",
            _sudo=True,
            label=label,
            worker=worker,
        )
        # A changed plist or script must restart the daemon (its current VM/job dies with it);
        # otherwise an unloaded daemon is just loaded. bootout is asynchronous (the worker's exit
        # trap deletes its VM first), and bootstrap fails with EIO until it has finished.
        script_changed = lambda: any(op.is_complete() and op.did_change() for op in (scripts[1], env))  # noqa: E731
        server.shell(
            name=f"worker {worker}: restart daemon",
            commands=[
                f"launchctl bootout system/{label} 2>/dev/null || true",
                f"for i in $(seq 1 60); do launchctl print system/{label} >/dev/null 2>&1 || break; sleep 1; done",
                f"launchctl bootstrap system {plist}",
            ],
            _sudo=True,
            _if=lambda r=rendered: (r.is_complete() and r.did_change()) or script_changed(),
        )
        server.shell(
            name=f"worker {worker}: daemon loaded",
            commands=[f"launchctl bootstrap system {plist}"],
            _sudo=True,
            _if=lambda r=rendered, lb=label: not ((r.is_complete() and r.did_change()) or script_changed())
            and not host.get_fact(LaunchdLoaded, label=lb, _sudo=True),
        )
