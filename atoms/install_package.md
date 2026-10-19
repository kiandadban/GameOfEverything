---
id: install_package
description: Installs system packages non-interactively.
required_vars: [package_name]
---
# Atom: Install Package
Ensures the necessary services are present for the lab.

### Logic Requirements:
1. Install packages non-interactively using the target distro's package manager — see the
   **Target OS** section for which manager to use and how to invoke it (on apt-based distros set
   `DEBIAN_FRONTEND=noninteractive` to avoid prompts).
2. Refresh the package index once before installing.
3. Install `<package_name>`, naming the package as it exists on the target distro.

### Testing Guidance:
1. Verify the package is installed using the target's package query (e.g. `dpkg -l | grep <package_name>` on apt-based distros).
2. If the package provides a service, confirm it is running with a process check (e.g. `pgrep <service_name>` or `service <service_name> status`) — `systemctl` is NOT available in these containers.

### Synthesis Guidance:
The Builder should combine multiple package requests into a single install command to improve container build speed.