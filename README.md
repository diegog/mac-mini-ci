<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/hero-dark.svg">
  <img alt="Mac + GitHub Actions" src=".github/hero-light.svg" height="80">
</picture>

# mac-mini-ci

**A Mac mini on a shelf that builds, signs, and ships your software.**

[![CI](https://github.com/diegog/mac-mini-ci/actions/workflows/ci.yml/badge.svg)](https://github.com/diegog/mac-mini-ci/actions/workflows/ci.yml)
[![macOS Tahoe 26.7](https://img.shields.io/badge/macOS_Tahoe-26.7-000000?logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![Mac mini M4](https://img.shields.io/badge/Mac_mini-M4_·_32_GB-555555?logo=apple&logoColor=white)](https://www.apple.com/mac-mini/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

</div>

Everything needed to turn a headless Mac mini into a self-hosted GitHub Actions runner.
Every job runs in a fresh macOS VM that is thrown away afterwards. Releases are signed and
notarized on the host, and a person approves each one.

## How it's built

| Layer | Tool |
| --- | --- |
| First boot | A person at the machine |
| Machine setup | [pyinfra](https://pyinfra.com) |
| GitHub config | [Pulumi](https://www.pulumi.com) |
| VM images | [Packer](https://www.packer.io) + [Tart](https://tart.run) |

## Before the tools can run

A new Mac mini has no SSH. Someone sits at it once with a display, a wired keyboard and mouse,
and Ethernet.

### At the machine

1. **Setup Assistant.** Create the admin account and keep its password: it is the volume owner,
   and `softwareupdate` needs it later. Choose **Set Up Later** on the Apple Account pane; signing
   in turns FileVault on and attaches Activation Lock. **Decline FileVault**; it blocks automatic
   login, and nothing starts after a reboot. Decline everything else.
2. **System Settings > General > Sharing.** Turn on **Remote Login** and **Screen Sharing**.
3. **System Settings > Privacy & Security.** Turn off Background Security Improvements if
   surprise restarts are unwelcome. No command line for this is known.
4. Check that `ssh` works from another machine. Unplug the display. pyinfra takes over from here.

### Later, over Screen Sharing, if needed

1. If pyinfra creates a separate user to run Tart, log in as that user once. Apple's
   virtualization framework needs a login keychain that a real login created; the terminal-only
   workaround in the Tart FAQ fails on Tahoe. If Tart runs as the admin from Setup Assistant,
   skip this: that login already happened.
2. Answer any privacy prompt that appears (Full Disk Access, Files & Folders). None should, if the
   runner and Tart keep their files outside Desktop, Documents and Downloads.

### Once, in a browser

1. Download the Xcode `.xip` from developer.apple.com (Apple Account with 2FA) and stage it for
   Packer. Repeat for each Xcode version. Software Update only offers the Command Line Tools, and
   the App Store needs an Apple Account signed in on the Mac.
2. Create the Developer ID Application certificate (Account Holder) and export the `.p12`.
3. Create an App Store Connect **Team** API key (Admin). Individual keys cannot use `notarytool`.
4. Register a GitHub App from a manifest and install it on the organization or repository.

Only the first group needs hands on the machine. Do it all in one sitting.

> **Status:** this is a plan, not a working system yet.
