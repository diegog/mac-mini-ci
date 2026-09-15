"""Data for every host. Secrets come from the environment (see machine/README.md), never from files in git."""

import os

# --- accounts -------------------------------------------------------------------------------
# `infra` is the Setup Assistant admin: sudo, OS updates, pyinfra's SSH user. It is never the
# user a CI job runs as.
admin_user = "infra"

# `ci` is a standard (non-admin) user created by this deploy. Tart, the VM loop and the release
# runner run as `ci`; it is the auto-login user so a login keychain and GUI session exist after
# every reboot (Virtualization.framework needs both since macOS 15.2).
ci_user = "ci"
ci_full_name = "CI"

# sudo password for `infra`. This deploy deliberately does not grant passwordless sudo, so every
# run needs it. Leave unset to be prompted interactively (needs a TTY).
_sudo_password = os.environ.get("MAC_MINI_INFRA_PASSWORD")

# Password for the `ci` account. Needed to create the account and to write /etc/kcpassword.
ci_password = os.environ.get("MAC_MINI_CI_PASSWORD")

# --- identity ---------------------------------------------------------------------------------
machine_name = "macmini-ci"
timezone = "GMT"  # macOS 27 systemsetup lists GMT but not UTC
ntp_server = "time.apple.com"

# --- toolchain --------------------------------------------------------------------------------
# https://github.com/Homebrew/brew/releases — the .pkg is Apple-silicon-only and installs to
# /opt/homebrew. Owned by `infra`; `ci` only executes what is installed.
homebrew_version = "7.0.1"
# GitHub's digest for that release's Homebrew.pkg asset; bump together with the version:
#   gh api repos/Homebrew/brew/releases/tags/7.0.1 --jq '.assets[] | select(.name=="Homebrew.pkg") | .digest'
homebrew_pkg_sha256 = "c71d94541adad139c16e92c7774e2635e157c6ed60174787398ecd84bbcd82a9"

# Tart base image for build VMs, pinned by digest (":latest" moves monthly).
# ghcr.io/cirruslabs/macos-tahoe-xcode:26.5 as of 2026-09-14 (68.8 GB download, 140 GB disk).
tart_image = (
    "ghcr.io/cirruslabs/macos-tahoe-xcode"
    "@sha256:61f6e857a3d65dd2f8daf9c51c7b837fa458bcc9181ae8556e645b534dab6bf6"
)

# --- network ----------------------------------------------------------------------------------
# Networks that macOS 15+ Local Network privacy should treat as non-local. Tart's NAT bridge and
# link-local only; the LaunchDaemons that talk to VMs are auto-allowed anyway (TN3179).
local_network_cidrs = ["192.168.64.0/24", "192.168.2.0/24", "169.254.0.0/16"]  # vmnet NAT, softnet, link-local

# Screen Sharing is off by default. `--data screen_sharing=true` turns it on for one deploy so you
# can VNC in (over an SSH tunnel) for the one-time GUI steps; the next plain run turns it off again.
screen_sharing = False

# --- GitHub Actions runners -------------------------------------------------------------------
# All optional: without a GitHub App the runner tasks print a notice and do nothing.
github_repo = os.environ.get("MAC_MINI_GITHUB_REPO")                       # owner/name
github_app_id = os.environ.get("MAC_MINI_GITHUB_APP_ID")
github_app_installation_id = os.environ.get("MAC_MINI_GITHUB_APP_INSTALLATION_ID")
github_app_key = os.environ.get("MAC_MINI_GITHUB_APP_KEY")                 # local path to the .pem

# Workers: each keeps one Tart VM slot busy (Apple allows two macOS VMs per host) and serves
# both lanes with one-job JIT runners.
workers = 2
vm_cpu = 4
vm_memory_mb = 8192
build_labels = ["self-hosted", "macOS", "ARM64", "mac-build"]
release_labels = ["self-hosted", "macOS", "ARM64", "mac-release"]
# Extra `tart run` flags, e.g. "--net-softnet-block=0.0.0.0/0 --net-softnet-allow=..." for an
# egress allow-list once there is a hostname-aware proxy to point at (GitHub publishes no IP
# ranges for the Actions service endpoints). Softnet already isolates VMs from the LAN.
extra_tart_run_args = ""

# Release signing material, mounted read-only into release VMs only. Local paths; optional.
signing_p12 = os.environ.get("MAC_MINI_SIGNING_P12")   # Developer ID Application .p12
notary_key = os.environ.get("MAC_MINI_NOTARY_KEY")     # App Store Connect team API key .p8

# The actions/runner build injected into every VM (the image's bundled copy ages out). Bump
# both together; GitHub refuses runners more than 30 days behind current:
#   gh api repos/actions/runner/releases/tags/v2.337.0 --jq '.assets[] | select(.name | test("osx-arm64")) | .digest'
runner_version = "2.337.0"
runner_sha256 = "5a2cd92908a93d7276a194e1de6008099f3e7946f3f8e14aa7a1a7b4a31fdec2"
