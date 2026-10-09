"""Platform seam: canonical spelling, case rule, and default prompt prefix (#44)."""

from conf_t.platform import Platform


def test_known_platforms_have_one_spelling_case_rule_and_prefix() -> None:
    cisco = Platform.of("cisco")
    assert cisco.known is True
    assert cisco.spelling == "Cisco"
    assert Platform.of("CISCO").spelling == "Cisco"
    assert cisco.ignores_case is True
    assert cisco.prefix == "Router#"

    linux = Platform.of("linux")
    assert linux.known is True
    assert linux.spelling == "Linux"
    assert linux.ignores_case is False
    assert linux.prefix == "user@ubuntu:~$"

    powershell = Platform.of("powershell")
    assert powershell.known is True
    assert powershell.spelling == "PowerShell"
    assert Platform.of("POWERSHELL").ignores_case is True
    assert powershell.prefix == "PS C:\\>"

    git = Platform.of("git")
    assert git.known is True
    assert git.spelling == "Git"
    assert git.ignores_case is False
    assert git.prefix == "user@ubuntu:~/project$"

    docker = Platform.of("Docker")
    assert docker.known is True
    assert docker.spelling == "Docker"
    assert docker.ignores_case is False
    assert docker.prefix == "user@ubuntu:~$"

    juniper = Platform.of("Juniper")
    assert juniper.known is False
    assert juniper.spelling == "Juniper"
    assert juniper.ignores_case is False
    assert juniper.prefix == "$"
    assert Platform.of("juniper").spelling == "juniper"

    blank = Platform.of("")
    assert blank.known is False
    assert blank.spelling == ""
    assert blank.ignores_case is False
    assert blank.prefix == "$"
    assert Platform.of("   ").prefix == "$"

    assert Platform.choices() == (
        "Cisco",
        "Linux",
        "PowerShell",
        "Git",
        "Docker",
        "Other",
    )
