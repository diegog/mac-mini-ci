"""Homebrew via its .pkg, owned by `infra`. The .pkg refuses to install without the Command Line
Tools and, on a host with no console user, without the HOMEBREW_PKG_USER plist."""

from pyinfra import host
from pyinfra.facts.files import File
from pyinfra.facts.server import Command
from pyinfra.operations import files, server

from mac_mini_ci.paths import BREW, CLT_GIT

admin = host.data.admin_user
version = host.data.homebrew_version
# In the admin's home, not /tmp: nobody else can pre-create the file. The sha256 is GitHub's
# published digest for the release asset; a mismatch fails the run before `installer` sees it.
pkg = f"/Users/{admin}/Homebrew-{version}.pkg"


def _no_brew() -> bool:
    return not host.get_fact(File, path=BREW)


files.download(
    name=f"Homebrew: download Homebrew.pkg {version}",
    src=f"https://github.com/Homebrew/brew/releases/download/{version}/Homebrew.pkg",
    dest=pkg,
    sha256sum=host.data.homebrew_pkg_sha256,
    temp_dir=f"/Users/{admin}",
    mode="644",
    _if=_no_brew,
)

server.shell(
    name=f"Homebrew: install user for the .pkg = {admin}",
    commands=[
        f"defaults write /var/tmp/.homebrew_pkg_user HOMEBREW_PKG_USER {admin}",
        "chown root:wheel /var/tmp/.homebrew_pkg_user.plist",
        "chmod 600 /var/tmp/.homebrew_pkg_user.plist",
        "chmod -N /var/tmp/.homebrew_pkg_user.plist",
    ],
    _sudo=True,
    _if=_no_brew,
)

server.shell(
    name="Homebrew: install .pkg",
    commands=[f"installer -pkg {pkg} -target /", f"rm -f {pkg}"],
    _sudo=True,
    _timeout=1800,
    _if=lambda: _no_brew() and bool(host.get_fact(File, path=CLT_GIT)),
)


def _analytics_persisted_off() -> bool:
    # `brew analytics state` honours HOMEBREW_NO_ANALYTICS from config.ENV and would always say
    # "disabled"; read the setting `brew analytics off` actually persists.
    out = host.get_fact(
        Command, command="git -C /opt/homebrew config --get homebrew.analyticsdisabled 2>/dev/null || true"
    )
    return (out or "").strip() == "true"


server.shell(
    name="Homebrew: analytics off",
    commands=[f"{BREW} analytics off"],
    _if=lambda: not _no_brew() and not _analytics_persisted_off(),
)
