# machine

The pyinfra deploy that turns the Mac mini into a runner host. It assumes the manual steps in the
top-level README are done: Setup Assistant finished, FileVault declined, Remote Login on, SSH key
for `infra` installed.

## Layout

```
inventory.py          the one host (override with MAC_MINI_HOST)
group_data/all.py     names, versions, image digest; secrets read from the environment
deploy.py             runs the tasks in order, reboots once if needed
tasks/                one file per concern
templates/            files rendered with host data
mac_mini_ci/          facts pyinfra lacks for macOS, kcpassword encoder, shared paths
```

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install pyinfra~=3.10
(umask 077; "${EDITOR:-vi}" .env)      # git-ignored; two lines:
                                      #   MAC_MINI_INFRA_PASSWORD=...   infra's password (sudo)
                                      #   MAC_MINI_CI_PASSWORD=...      password for the new ci account
set -a; . ./.env; set +a
.venv/bin/pyinfra inventory.py deploy.py --dry     # connect, read facts, list changes
.venv/bin/pyinfra inventory.py deploy.py           # apply
```

Do not paste the passwords into a heredoc at the prompt: shell history keeps them.

`--dry` overstates: pyinfra decides `_if` guards only at execute time, so every guarded shell step
shows as a change. The real run skips what is already done; the one step that always runs is the
`sshd -t` assertion. `-vv` prints the commands.

Run from this directory; paths in `templates/` and `tasks/` are relative to it.

The inventory pins the host key (`ssh_strict_host_key_checking: yes`). When the address changes
(Ethernet plugged in), add the new address to `~/.ssh/known_hosts` first — `ssh infra@<new-ip>`
once and confirm the fingerprint is the one you already trust. A `ServerAliveInterval 30` entry
for the host in `~/.ssh/config` keeps the long image pull alive; pyinfra honours it.

## What it does

| Task | Result |
| --- | --- |
| sanity | Refuses to run unless: macOS, Apple silicon, SSH user is `infra`, FileVault off, sshd honours drop-ins, ≥300 GB free |
| access | sshd drop-in: keys only, `infra` only, no root; rolled back if sshd rejects it. Remote Login stays on. Screen Sharing off |
| identity | `macmini-ci` as HostName/LocalHostName/ComputerName, GMT, NTP on |
| power | Never sleeps, wakes for network, starts when power is connected (or after power failure), no login-window screensaver, developer mode |
| updates | macOS ≤26: no automatic macOS/App Store installs or downloads, XProtect data stays on. macOS 27+: not scriptable — prints a notice; set it in System Settings once |
| network | Local Network privacy: Tart's NAT and link-local treated as non-local (needs the reboot) |
| ci_user | Standard user `ci`, no first-login Setup Assistant, auto-login, no screensaver or App Nap |
| reboot | Once, whenever a Local Network or auto-login change is pending — recorded on the host, so it survives an interrupted run; then checks `ci` owns the console |
| clt | Xcode Command Line Tools (git, python3) |
| homebrew | Homebrew.pkg (sha256-pinned), owned by `infra`, analytics off |
| tart | `tart`, `softnet` (setuid), `jq`; base image pulled into `/Users/ci/.tart` |
| runners | App key (0600, `ci` only), the pinned runner tarball, `runners.env`, the `github-app-token` and `mac-worker` scripts, optional signing files; two LaunchDaemons (`ci.mac-mini-ci.worker1/2`) |

## Runner workers

Need a GitHub App (repository permission Administration: write, installed on the repo) and four
more `.env` lines: `MAC_MINI_GITHUB_REPO`, `MAC_MINI_GITHUB_APP_ID`,
`MAC_MINI_GITHUB_APP_INSTALLATION_ID`, `MAC_MINI_GITHUB_APP_KEY` (path to the .pem). Without them
the runner task prints a notice and does nothing.

Two workers, one Tart VM slot each (Apple's limit). Each keeps a warm build VM booted with nothing
registered, polls GitHub for queued jobs labelled `mac-build` or `mac-release`, claims one (a lock
directory per job id, so the workers never double-book), mints a one-job JIT runner, installs the
pinned runner into the VM from the shared cache, and runs it. A release job gets a fresh VM with
the signing directory mounted read-only (`/Volumes/My Shared Files/signing`); the `.p12` password
is a GitHub environment secret, never on the host. A watchdog tears down a runner whose job never
arrives. After the job the VM is deleted and the next warm one boots.

- Everything runs as `ci`; the App key is readable by `ci`. With repo-level JIT the App must hold
  Administration: write, which is broader than runners; an org would narrow it to "Self-hosted
  runners". Jobs run in VMs, so a job cannot read the key.
- Build VMs are isolated from the LAN by softnet but have full internet egress: GitHub publishes
  no IP ranges for the Actions service endpoints, so an allow-list needs a hostname-aware proxy
  first (`extra_tart_run_args` is the hook).
- Build jobs start immediately (warm VM); release jobs pay ~45 s for the fresh VM.
- To ship signing material: set `MAC_MINI_SIGNING_P12` and `MAC_MINI_NOTARY_KEY` to local paths in
  `.env` and rerun; gate the release workflow with an environment that has required reviewers.
- Runner version: bump `runner_version` and `runner_sha256` together; nothing else to restart.
- Logs: `/Users/ci/Library/Logs/mac-mini-ci/worker{1,2}.log`.
- Canary: run the "Mac canary" workflow from the Actions tab; it exercises both lanes.

## What it deliberately does not do

- No passwordless sudo. `infra` keeps password sudo; pyinfra supplies it. Nothing that runs as `ci`
  can escalate — except that during a deploy pyinfra's askpass puts `infra`'s password on the
  argv of every sudo'd command, and macOS lets local users read other users' argv. So: do not
  deploy while untrusted work runs as `ci`; the runner services (next milestone) get booted out
  for the duration of a deploy.
- No secure token for `ci`. FileVault is off and OS updates are `infra`'s job; a token would only
  put `infra`'s password on `sysadminctl`'s argv.
- Background Security Improvements: Apple offers no command for the toggle. System Settings only.

## Screen Sharing, when you need it

```sh
.venv/bin/pyinfra inventory.py deploy.py --data screen_sharing=true
ssh -N -L 5900:localhost:5900 infra@10.0.10.215   # then open vnc://localhost:5900
.venv/bin/pyinfra inventory.py deploy.py         # turns it off again
```

## Check on the host after the first run

macOS 27 is new; these are the things the research could not verify on it.

1. Resolved on 27.0: neither `softwareupdate --schedule off` nor the com.apple.SoftwareUpdate keys
   do anything any more. Set System Settings > General > Software Update > Automatic Updates by hand
   (everything off except security responses), over Screen Sharing.
2. Over Screen Sharing, once: after the auto-login the `ci` session shows the Desktop, not the
   Apple Account / Siri / Screen Time setup panes.
3. `sudo -u ci /opt/homebrew/bin/tart run --no-graphics <clone>` works from a LaunchDaemon with
   `UserName=ci` and `SessionCreate=true` (the keychain requirement).
4. `codesign` under that daemon works with `SessionCreate` true; if not, false.
5. `pmset -g custom` after the first run: which of `autorestartatconnect` / `autorestart` took.
