"""Distro profiles — per-OS configuration for target containers.

A ``DistroProfile`` is a small, reusable record describing how to bring up a
target container for one operating system: which base image to run, which
package manager it uses, and which base packages to install so the
self-installing deploy scripts work.

The ``System.os`` field selects a profile by its canonical name. New OSes are
added by registering another ``DistroProfile`` here — nothing else in the
container/packaging layers needs to know the concrete image.
"""

from __future__ import annotations

from dataclasses import dataclass

# Base packages installed into every apt-based target container, so the
# self-installing deploy scripts have the tools they rely on (curl, ssh, etc.).
# Both Ubuntu and Debian ship these under identical names.
APT_BASE_PACKAGES: tuple[str, ...] = (
    # Core utilities
    "curl",
    "wget",
    "ca-certificates",
    "gnupg",
    "lsb-release",
    # Networking tools
    "iproute2",
    "net-tools",
    "iputils-ping",
    # Process management
    "procps",
    # Common attack surface packages (pre-installed on real servers)
    "sudo",
    "openssh-server",
    "sshpass",
)


@dataclass(frozen=True)
class DistroProfile:
    """Everything the container layer needs to stand up a target for one OS."""

    name: str  # canonical name, e.g. "ubuntu"
    image: str  # docker base image, e.g. "ubuntu:22.04"
    package_manager: str  # "apt" (room for "dnf" etc. later)
    base_packages: tuple[str, ...]

    def bootstrap_command(self) -> str:
        """Bash command that installs the base packages into a fresh container."""
        if self.package_manager == "apt":
            packages = " ".join(self.base_packages)
            return (
                "apt-get update -y && "
                "DEBIAN_FRONTEND=noninteractive apt-get install -y "
                f"{packages}"
            )
        raise ValueError(
            f"DistroProfile {self.name!r}: unsupported package manager "
            f"{self.package_manager!r}"
        )


# Canonical profiles, keyed by canonical OS name.
_PROFILES: dict[str, DistroProfile] = {
    "ubuntu": DistroProfile(
        name="ubuntu",
        image="ubuntu:22.04",
        package_manager="apt",
        base_packages=APT_BASE_PACKAGES,
    ),
    "debian": DistroProfile(
        name="debian",
        image="debian:12",
        package_manager="apt",
        base_packages=APT_BASE_PACKAGES,
    ),
}

# Legacy / alternate spellings mapped onto a canonical profile name.
_ALIASES: dict[str, str] = {
    "ubuntu_22_04": "ubuntu",
    "ubuntu2204": "ubuntu",
    "debian_12": "debian",
    "debian12": "debian",
    "bookworm": "debian",
}


def normalize_os(os: str) -> str:
    """Return the canonical distro name for ``os``, or raise on an unknown OS."""
    key = os.strip().lower()
    key = _ALIASES.get(key, key)
    if key not in _PROFILES:
        raise ValueError(
            f"Unknown OS {os!r}. Supported: {sorted(_PROFILES)} "
            f"(aliases: {sorted(_ALIASES)})"
        )
    return key


def get_profile(os: str) -> DistroProfile:
    """Resolve the ``DistroProfile`` for ``os`` (canonical name or alias)."""
    return _PROFILES[normalize_os(os)]


def available_distros() -> list[str]:
    """Canonical names of all registered distro profiles."""
    return sorted(_PROFILES)