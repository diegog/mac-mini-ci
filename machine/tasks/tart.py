"""Tart (+ softnet) from the openai/tools tap; base image pulled into `ci`'s ~/.tart.

Homebrew ops run as `infra` (the prefix owner). `ci` never runs brew; it only executes what is
installed. Tap trust is per user and mandatory since Homebrew 6."""

from pyinfra import host
from pyinfra.facts.brew import BrewItemKind
from pyinfra.operations import brew, server

from mac_mini_ci.facts import SoftnetSuid, TartImages
from mac_mini_ci.paths import SOFTNET, TART

ci = host.data.ci_user
image = host.data.tart_image
digest = image.split("@", 1)[1] if "@" in image else image

# Trust first: Homebrew 7's `brew tap` validates every formula after cloning and refuses an
# untrusted tap, so the trust must exist before the tap does. brew.tap must still be told
# trusted=True: its default (False) actively untrusts the tap.
brew.trust(
    name="Homebrew: trust tap openai/tools", items="openai/tools", kind=BrewItemKind.TAP, trusted=True
)
brew.tap(name="Homebrew: tap openai/tools", src="openai/tools", trusted=True)

# Short names on purpose: pyinfra matches `brew list --versions`, which prints short names, so
# "openai/tools/tart" would reinstall on every run.
brew.packages(name="Homebrew: tart, softnet, jq", packages=["tart", "softnet", "jq"])

# Tart only fixes softnet's setuid bit interactively; under launchd it must already be set. The
# Homebrew path is a symlink and the Cellar path changes on upgrade, so re-check every run.
server.shell(
    name="softnet: setuid root",
    commands=[f'P=$(readlink -f {SOFTNET}) && chown root "$P" && chmod u+s "$P"'],
    _sudo=True,
    _if=lambda: not host.get_fact(SoftnetSuid),
)

# ~69 GB. Six hours covers slow links; the pull resumes cached layers on retry. Ethernet, please.
server.shell(
    name=f"Tart: pull base image as {ci}",
    commands=[f"{TART} pull --concurrency 4 {image}"],
    _sudo=True,
    _sudo_user=ci,
    _timeout=6 * 3600,
    _retries=2,
    _retry_delay=60,
    _if=lambda: not any(
        digest in name for name in host.get_fact(TartImages, _sudo=True, _sudo_user=ci)
    ),
)
