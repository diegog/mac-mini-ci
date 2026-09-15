"""Refuse to run against the wrong machine or an unsafe state. Runs during prepare, so `--dry` checks it too."""

from pyinfra import host
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.server import Arch, Command, Kernel, MacosVersion, User

from mac_mini_ci.facts import FileVaultOn

if host.get_fact(Kernel) != "Darwin":
    raise DeployError("refusing to deploy: not macOS")

problems = []

if host.get_fact(Arch) != "arm64":
    problems.append("not Apple silicon")
if host.get_fact(User) != host.data.admin_user:
    problems.append(f"SSH user must be {host.data.admin_user}")
if host.get_fact(FileVaultOn):
    problems.append("FileVault is on; auto-login and unattended reboots need it off")

# Command facts return the output as one string (None when empty).
sshd_include = (
    host.get_fact(Command, command="grep -c '^Include /etc/ssh/sshd_config.d/' /etc/ssh/sshd_config || true")
    or "0"
).strip()
if sshd_include == "0":
    problems.append("/etc/ssh/sshd_config has no Include for sshd_config.d; drop-ins would be ignored")

free_gb = int((host.get_fact(Command, command="df -g /Users | awk 'NR==2{print $4}'") or "0").strip() or 0)
if free_gb < 300:
    problems.append(
        f"only {free_gb} GB free on /Users; the Xcode image needs ~70 GB download, 140 GB disk, "
        "and headroom for two clones"
    )

if not host.data.ci_password:
    problems.append("MAC_MINI_CI_PASSWORD is not set")

if problems:
    raise DeployError("refusing to deploy: " + "; ".join(problems))

host.noop(f"macOS {host.get_fact(MacosVersion)} on {host.get_fact(Arch)}, FileVault off, {free_gb} GB free")
