"""ForkPrApprovalPolicy: the repository's "fork pull request workflows from outside collaborators"
setting, which the GitHub provider does not model. Backed by
PUT /repos/{owner}/{repo}/actions/permissions/fork-pr-contributor-approval."""

from __future__ import annotations

import pulumi
from pulumi import dynamic

from github_app import api, installation_token

DEFAULT_POLICY = "first_time_contributors_new_to_github"  # GitHub's own default


class _Provider(dynamic.ResourceProvider):
    def _token(self, props: dict) -> str:
        return installation_token(props["app_id"], props["installation_id"], props["pem"])

    def _set(self, props: dict, policy: str) -> None:
        api("PUT", f"/repos/{props['repository']}/actions/permissions/fork-pr-contributor-approval",
            self._token(props), {"approval_policy": policy})

    def create(self, props):
        self._set(props, props["approval_policy"])
        return dynamic.CreateResult(id_=props["repository"], outs=props)

    def update(self, _id, _olds, news):
        self._set(news, news["approval_policy"])
        return dynamic.UpdateResult(outs=news)

    def read(self, id_, props):
        current = api("GET", f"/repos/{props['repository']}/actions/permissions/fork-pr-contributor-approval",
                      self._token(props))
        return dynamic.ReadResult(id_=id_, outs={**props, "approval_policy": current["approval_policy"]})

    def diff(self, _id, olds, news):
        return dynamic.DiffResult(changes=olds.get("approval_policy") != news.get("approval_policy"))

    def delete(self, _id, props):
        self._set(props, DEFAULT_POLICY)


class ForkPrApprovalPolicy(dynamic.Resource):
    """approval_policy: first_time_contributors_new_to_github | first_time_contributors | all_external_contributors"""

    approval_policy: pulumi.Output[str]

    def __init__(self, name: str, *, repository: pulumi.Input[str], approval_policy: pulumi.Input[str],
                 app_id: pulumi.Input[str], installation_id: pulumi.Input[str], pem: pulumi.Input[str],
                 opts: pulumi.ResourceOptions | None = None):
        super().__init__(_Provider(), name, {
            "repository": repository,
            "approval_policy": approval_policy,
            "app_id": app_id,
            "installation_id": installation_id,
            "pem": pulumi.Output.secret(pem),
        }, opts)
