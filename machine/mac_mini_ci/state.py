"""Cross-task state for one deploy run."""

from collections import defaultdict

# Operations whose change means the host must reboot, keyed by host name.
reboot_triggers: dict[str, list] = defaultdict(list)

# Recorded on the host when a trigger changed, cleared after a confirmed reboot, so an interrupted
# run cannot lose the reboot (on the next run the triggers are already satisfied).
REBOOT_MARKER = "/var/db/.mac-mini-ci-reboot-pending"
