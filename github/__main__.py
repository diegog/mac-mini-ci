"""GitHub-side configuration for mac-mini-ci: the repository, its Actions policy, the release gate.

Authenticates as the same GitHub App the Mac mini uses (repository Administration: write). The
App itself and its installation are not managed here: GitHub has no API to create Apps.
"""

import os

import pulumi
import pulumi_github as github

from fork_pr_policy import ForkPrApprovalPolicy

config = pulumi.Config()
owner = config.require("owner")
repo_name = config.require("repository")
reviewer_ids = config.require_object("reviewerIds")  # GitHub user ids allowed to approve releases
app_id = os.environ["MAC_MINI_GITHUB_APP_ID"]
installation_id = os.environ["MAC_MINI_GITHUB_APP_INSTALLATION_ID"]
pem = open(os.path.expanduser(os.environ["MAC_MINI_GITHUB_APP_KEY"])).read()

provider = github.Provider(
    "app",
    owner=owner,
    app_auth=github.ProviderAppAuthArgs(id=app_id, installation_id=installation_id, pem_file=pem),
)
opts = pulumi.ResourceOptions(provider=provider)

# The repository already exists (imported); protect=True makes `pulumi destroy` refuse to delete it.
repo = github.Repository(
    "repo",
    name=repo_name,
    description="A Mac mini on a shelf that builds, signs, and ships your software.",
    visibility="public",
    has_issues=True,
    has_projects=False,
    has_wiki=False,
    delete_branch_on_merge=True,
    allow_merge_commit=True,
    allow_squash_merge=True,
    allow_rebase_merge=True,
    opts=pulumi.ResourceOptions(provider=provider, protect=True),
)

# Dependabot: alerts for known-vulnerable dependencies, with automatic fix PRs. Version bumps for
# the SHA-pinned actions come from .github/dependabot.yml (nobody updates commit hashes by hand).
alerts = github.RepositoryVulnerabilityAlerts("vulnerability-alerts", repository=repo.name, opts=opts)
github.RepositoryDependabotSecurityUpdates(
    "dependabot-security-updates",
    repository=repo.name,
    enabled=True,
    opts=pulumi.ResourceOptions(provider=provider, depends_on=[alerts]),
)

# Only GitHub-authored and verified-creator actions may run, and they must be pinned by commit.
github.ActionsRepositoryPermissions(
    "actions-permissions",
    repository=repo.name,
    enabled=True,
    allowed_actions="selected",
    allowed_actions_config=github.ActionsRepositoryPermissionsAllowedActionsConfigArgs(
        github_owned_allowed=True,
        verified_allowed=True,
        patterns_alloweds=[],
    ),
    sha_pinning_required=True,
    opts=opts,
)

# Nothing from a fork runs on any runner until a person approves it.
ForkPrApprovalPolicy(
    "fork-pr-approval",
    repository=pulumi.Output.concat(owner, "/", repo.name),
    approval_policy="all_external_contributors",
    app_id=app_id,
    installation_id=installation_id,
    pem=pem,
    opts=pulumi.ResourceOptions(depends_on=[repo]),
)

# The release gate: jobs using this environment wait for one of the reviewers. The signing
# keychain password lives here as a secret, set out of band (`gh secret set --env release`).
release = github.RepositoryEnvironment(
    "release",
    repository=repo.name,
    environment="release",
    reviewers=[github.RepositoryEnvironmentReviewerArgs(users=reviewer_ids)],
    prevent_self_review=False,  # a one-person project approves its own releases
    can_admins_bypass=False,
    deployment_branch_policy=github.RepositoryEnvironmentDeploymentBranchPolicyArgs(
        protected_branches=False,
        custom_branch_policies=True,
    ),
    opts=opts,
)
github.RepositoryEnvironmentDeploymentPolicy(
    "release-from-main",
    repository=repo.name,
    environment=release.environment,
    branch_pattern="main",
    opts=opts,
)

# Non-secret identifiers the release workflow needs (`vars.*`). The two secrets are set by hand:
# SIGNING_P12_PASSWORD (environment) — and the key files themselves live on the Mac.
for variable_name, value in config.require_object("releaseVariables").items():
    github.ActionsEnvironmentVariable(
        f"release-var-{variable_name.lower().replace('_', '-')}",
        repository=repo.name,
        environment=release.environment,
        variable_name=variable_name,
        value=value,
        opts=opts,
    )

# main: changes arrive by pull request with CI green; no force-pushes or deletion. Repository
# admins may bypass for emergencies.
github.RepositoryRuleset(
    "main",
    name="main",
    repository=repo.name,
    target="branch",
    enforcement="active",
    conditions=github.RepositoryRulesetConditionsArgs(
        ref_name=github.RepositoryRulesetConditionsRefNameArgs(includes=["~DEFAULT_BRANCH"], excludes=[]),
    ),
    rules=github.RepositoryRulesetRulesArgs(
        deletion=True,
        non_fast_forward=True,
        pull_request=github.RepositoryRulesetRulesPullRequestArgs(
            required_approving_review_count=0,
            dismiss_stale_reviews_on_push=False,
            require_code_owner_review=False,
            require_last_push_approval=False,
            required_review_thread_resolution=False,
        ),
        required_status_checks=github.RepositoryRulesetRulesRequiredStatusChecksArgs(
            required_checks=[github.RepositoryRulesetRulesRequiredStatusChecksRequiredCheckArgs(context="Check repository")],
            strict_required_status_checks_policy=False,
        ),
    ),
    bypass_actors=[github.RepositoryRulesetBypassActorArgs(actor_id=5, actor_type="RepositoryRole", bypass_mode="always")],
    opts=opts,
)

pulumi.export("repository", pulumi.Output.concat(owner, "/", repo.name))
pulumi.export("release_environment", release.environment)
