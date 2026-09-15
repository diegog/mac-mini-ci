"""One host. Override the address with MAC_MINI_HOST when the IP changes (e.g. after plugging in Ethernet)."""

import os

mac_minis = [
    (
        os.environ.get("MAC_MINI_HOST", "10.0.10.215"),
        {
            "ssh_user": "infra",
            "ssh_strict_host_key_checking": "yes",
        },
    ),
]
