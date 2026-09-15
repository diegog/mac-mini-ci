"""GitHub App credentials and helper scripts for `ci`. Skipped (with a notice) when no App is configured."""

from pyinfra import host
from pyinfra.operations import files, server

ci = host.data.ci_user
HOME = f"/Users/{ci}"
BIN = f"{HOME}/mac-mini-ci/bin"
KEY = f"{HOME}/.config/mac-mini-ci/github-app.pem"
CACHE = f"{HOME}/mac-mini-ci/runner"
version = host.data.runner_version
TARBALL = f"actions-runner-osx-arm64-{version}.tar.gz"

configured = all(
    [host.data.github_repo, host.data.github_app_id, host.data.github_app_installation_id, host.data.github_app_key]
)

if not configured:
    host.noop("GitHub App not configured (MAC_MINI_GITHUB_*): skipping the runner lanes")
else:
    for path in (f"{HOME}/.config", f"{HOME}/.config/mac-mini-ci", f"{HOME}/mac-mini-ci", BIN, CACHE, f"{HOME}/Library/Logs/mac-build"):
        files.directory(name=f"dir {path}", path=path, user=ci, group="staff", mode="700", _sudo=True)

    # The pinned runner build, cached once: unpacked for the release runner, shared read-only
    # into every build VM.
    files.download(
        name=f"runner {version}: cache tarball",
        src=f"https://github.com/actions/runner/releases/download/v{version}/{TARBALL}",
        dest=f"{CACHE}/{TARBALL}",
        sha256sum=host.data.runner_sha256,
        mode="644",
        _sudo=True,
        _sudo_user=ci,
    )

    # The App key: only `ci` reads it, only through github-app-token.
    key = files.put(
        name="GitHub App private key",
        src=host.data.github_app_key,
        dest=KEY,
        user=ci,
        group="staff",
        mode="600",
        _sudo=True,
        _temp_dir=f"/Users/{host.data.admin_user}/.pyinfra-tmp",
    )

    env = files.template(
        name="mac-build.env",
        src="templates/mac-build.env.j2",
        dest=f"{HOME}/mac-mini-ci/mac-build.env",
        user=ci,
        group="staff",
        mode="600",
        _sudo=True,
    )

    scripts = [
        files.put(
            name=f"script {name}",
            src=f"files/{name}",
            dest=f"{BIN}/{name}",
            user=ci,
            group="staff",
            mode="755",
            _sudo=True,
        )
        for name in ("github-app-token", "mac-build-slot")
    ]

    # Prove the whole chain (key -> JWT -> installation token) from the host, as ci, whenever
    # any of its inputs changed.
    server.shell(
        name="GitHub App: token helper works as ci",
        commands=[f"{BIN}/github-app-token >/dev/null"],
        _sudo=True,
        _sudo_user=ci,
        _if=lambda: any(op.is_complete() and op.did_change() for op in (key, env, *scripts)),
    )
