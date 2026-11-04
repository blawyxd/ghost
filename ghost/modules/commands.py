SAVED_COMMANDS = [
    (
        "Kernel version",
        "uname -r",
        "Show the currently running Linux kernel.",
    ),
    (
        "Failed system services",
        "systemctl --failed",
        "List services that failed to start.",
    ),
    (
        "GPU information",
        "nvidia-smi",
        "Show NVIDIA GPU usage, temperature and processes.",
    ),
    (
        "Package cache size",
        "du -sh /var/cache/pacman/pkg",
        "Inspect the pacman package cache size. Does not delete anything.",
    ),
    (
        "Recent boot errors",
        "journalctl -b -p err --no-pager",
        "Show errors from the current boot.",
    ),
]
