"""macOS 15+ Local Network privacy: treat Tart's NAT bridge as non-local so nothing ever needs the
GUI prompt. The LaunchDaemons that talk to VMs are auto-allowed regardless (TN3179); this is
belt-and-braces for anything started from the GUI session. Takes effect after a reboot."""

import shlex

from pyinfra import host
from pyinfra.operations import server

from mac_mini_ci.facts import DefaultsArray
from mac_mini_ci.state import reboot_triggers

DOMAIN = "com.apple.network.local-network"
cidrs = list(host.data.local_network_cidrs)
quoted = " ".join(shlex.quote(c) for c in cidrs)

for key in ("AllowedEthernetLocalNetworkAddresses", "AllowedWiFiLocalNetworkAddresses"):
    op = server.shell(
        name=f"Local Network privacy: {key}",
        commands=[f"defaults write {DOMAIN} {key} -array {quoted}"],
        _sudo=True,
        _if=lambda k=key: host.get_fact(DefaultsArray, domain=DOMAIN, key=k, _sudo=True) != cidrs,
    )
    reboot_triggers[host.name].append(op)
