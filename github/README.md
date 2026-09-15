# github

Pulumi program for the GitHub side of mac-mini-ci: the repository, its Actions policy, the release
gate, and the `main` ruleset. It authenticates as the same GitHub App the Mac mini uses, so there is
no personal access token anywhere. The App and its installation are created by hand (GitHub has
no API for that); see the top-level README.

## Run

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
(umask 077; "${EDITOR:-vi}" .env)   # PULUMI_CONFIG_PASSPHRASE=<any long random string; back it up>
set -a; . ../machine/.env; . ./.env; set +a       # MAC_MINI_GITHUB_* come from machine/.env
pulumi login --local                              # state under ~/.pulumi, encrypted with the passphrase
pulumi preview
pulumi up
```

`pulumi` itself is installed with `mise use -g pulumi@latest`. The stack is `main`
(`Pulumi.main.yaml`); the state lives on this workstation only — move it with
`pulumi stack export`/`import` if that ever needs to change.

## What it manages

| Resource | Setting |
| --- | --- |
| `github.Repository` (imported, protected) | description, public, issues on, wiki/projects off, delete branch on merge, all merge methods |
| `github.ActionsRepositoryPermissions` | only GitHub-authored and verified-creator actions; **SHA pinning required** (pin with `uses: owner/action@<commit>  # vN`) |
| `ForkPrApprovalPolicy` (dynamic, `fork_pr_policy.py`) | fork pull request workflows need approval from a maintainer for **all** external contributors |
| `github.RepositoryEnvironment` `release` | required reviewer(s) from `reviewerIds`; deployments only from `main` |
| `github.RepositoryRuleset` `main` | changes by pull request with the `Check repository` check green; no force-push or deletion; repository admins may bypass |

Not managed here: the GitHub App and its installation; the `release` environment's secrets
(`gh secret set --env release SIGNING_KEYCHAIN_PASSWORD`); self-hosted runners (they register
themselves, see `machine/`).

## Notes

- The repository resource is `protect=True`: `pulumi destroy` refuses to delete it. Everything
  else is safe to destroy and recreate.
- The fork-PR policy is a dynamic resource because the provider has no type for it; destroying it
  resets GitHub's default (approval only for first-time contributors new to GitHub).
- Runner groups need an organization, so there are none. Moving the repository into an org would
  add `github.ActionsRunnerGroup` here and narrow the App's permission to "Self-hosted runners".
