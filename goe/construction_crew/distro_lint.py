"""Distro lint — a deterministic backstop for distro-correctness of generated output.

The construction-crew agents are *told* the target distro (the Target OS context injected
into their prompts), but that guidance is advisory: an LLM can still emit an Ubuntu-ism.
This lint reads the generated deploy script and attack procedure and flags commands that
are wrong for the target ``DistroProfile`` — before the build deploys them. It is the
deterministic counterpart to the probabilistic agents: prevention lives in the prompts and
the profile, this is the net that catches residual leakage.

Scope: it checks within-family breakage that matters for the distros we support today
(Ubuntu + Debian). Each rule is keyed off the profile, not a hardcoded distro, so it stays
correct as new profiles are registered:

* ``systemctl`` when the profile has no systemd (fails in these containers either way);
* genuinely Ubuntu-only tooling (PPAs / ``add-apt-repository``) when the target is not Ubuntu;
* a canonical package name where the profile aliases it to a different real name on this
  distro (e.g. ``netcat`` -> ``netcat-openbsd`` on Debian).

It is intentionally conservative: high-confidence tokens only, so a clean build produces no
findings and the net never derails a correct scenario.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from goe.distros import DistroProfile
    from goe.models.procedure import Procedure


@dataclass(frozen=True)
class LintFinding:
    """One distro-correctness problem found in generated output.

    where    "deploy_script" or "procedure:<step_id>" — which artifact carried it.
    token    the offending text (e.g. "systemctl").
    message  what is wrong on this distro and how to fix it.
    """

    where: str
    token: str
    message: str


# Ubuntu-only tokens: things that exist on Ubuntu but not on other Debian-family distros.
# (Deliberately NOT including /etc/update-motd.d — it is valid on Debian too.)
_UBUNTU_ONLY: tuple[tuple[str, str, str], ...] = (
    (r"\badd-apt-repository\b", "add-apt-repository",
     "`add-apt-repository` (PPAs) is Ubuntu-only and is not available on {distro}."),
    (r"(?<![\w/])ppa:", "ppa:",
     "PPAs are an Ubuntu-only package source and are not available on {distro}."),
)


def _commands(procedure: "Procedure | None") -> list[tuple[str, str]]:
    """Extract (where, command-text) pairs from a procedure's shell-bearing steps."""
    out: list[tuple[str, str]] = []
    for step in getattr(procedure, "procedure", None) or []:
        action = getattr(step, "action", None)
        text = getattr(action, "command", None) or getattr(action, "script", None)
        if text:
            out.append((f"procedure:{step.step_id}", text))
    return out


def _lint_text(profile: "DistroProfile", where: str, text: str) -> list[LintFinding]:
    findings: list[LintFinding] = []

    # 1. systemd — keyed off the profile's init model, not the distro name.
    if not profile.has_systemd and re.search(r"\bsystemctl\b", text):
        findings.append(LintFinding(
            where, "systemctl",
            f"`systemctl` is used, but {profile.name} runs without systemd in these containers "
            "— start/reload the service with its own tool or a background process instead."))

    # 2. Ubuntu-only tooling — only when the target is not Ubuntu.
    if profile.name != "ubuntu":
        for pattern, token, msg in _UBUNTU_ONLY:
            if re.search(pattern, text):
                findings.append(LintFinding(where, token, msg.format(distro=profile.name)))

    # 3. Package-name aliases — a canonical name installed where this distro renames it.
    for canonical, real in (profile.package_aliases or {}).items():
        if canonical == real:
            continue
        installs_canonical = re.search(
            rf"install\b[^\n]*\b{re.escape(canonical)}\b", text)
        if installs_canonical and real not in text:
            findings.append(LintFinding(
                where, canonical,
                f"package `{canonical}` is installed, but on {profile.name} the package is "
                f"`{real}` — use the distro's package name."))

    return findings


def lint(
    profile: "DistroProfile",
    deploy_script: str | None,
    procedure: "Procedure | None" = None,
) -> list[LintFinding]:
    """Return distro-correctness findings for the generated deploy script and procedure.

    An empty list means nothing suspect was found for ``profile``.
    """
    sources: list[tuple[str, str]] = []
    if deploy_script:
        sources.append(("deploy_script", deploy_script))
    sources.extend(_commands(procedure))

    findings: list[LintFinding] = []
    for where, text in sources:
        findings.extend(_lint_text(profile, where, text))
    return findings
