"""One Platform: canonical spelling, the case rule, and the default prompt prefix."""

from __future__ import annotations

from dataclasses import dataclass

# Match ignores case. The value is the spelling Lessons and stats use.
_CANONICAL = {
    "cisco": "Cisco",
    "linux": "Linux",
    "powershell": "PowerShell",
    "git": "Git",
    "docker": "Docker",
}

_IGNORE_CASE = frozenset({"cisco", "powershell"})

_PREFIX = {
    "cisco": "Router#",
    "linux": "user@ubuntu:~$",
    "docker": "user@ubuntu:~$",
    "powershell": "PS C:\\>",
    "git": "user@ubuntu:~/project$",
}

_CHOICES = ("Cisco", "Linux", "PowerShell", "Git", "Docker", "Other")


@dataclass(frozen=True)
class Platform:
    """A command environment named on a Lesson.

    A known name matches in any case and answers the canonical spelling.
    An unknown name keeps the spelling that was stored and grades with case.
    """

    stored: str

    @classmethod
    def of(cls, spelling: str) -> Platform:
        return cls(stored=spelling)

    @staticmethod
    def choices() -> tuple[str, ...]:
        """Wizard list: the known Platforms, then Other."""
        return _CHOICES

    @property
    def known(self) -> bool:
        return self.stored.casefold() in _CANONICAL

    @property
    def spelling(self) -> str:
        """Canonical spelling for a known Platform, otherwise the stored spelling."""
        return _CANONICAL.get(self.stored.casefold(), self.stored)

    @property
    def ignores_case(self) -> bool:
        """Cisco and PowerShell ignore case. Every other Platform keeps case."""
        return self.stored.casefold() in _IGNORE_CASE

    @property
    def prefix(self) -> str:
        """Suggested prompt prefix. An empty or unknown name uses `$`."""
        if not self.stored.strip():
            return "$"
        return _PREFIX.get(self.stored.casefold(), "$")
