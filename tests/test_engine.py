from conf_t.models import Lesson, Task
from conf_t.engine import (
    LessonLoader,
    collect_all_tags,
    filter_lessons_by_tags,
    format_display_answer,
    lesson_matches_tags,
    parse_tags_csv,
    sort_lessons_by_curriculum,
    validate_input,
)

# 1. Tests for validate_input
def test_validate_input_cisco_case_insensitive():
    task = Task(
        id="test_task",
        prompt="Enter config mode",
        prefix="Router#",
        expected="^configure\\s+terminal$",
        aliases=["conf t", "config t"]
    )
    # Cisco platform is case-insensitive
    assert validate_input("configure terminal", task, "Cisco") is True
    assert validate_input("CONFIGURE TERMINAL", task, "Cisco") is True
    assert validate_input("conf t", task, "Cisco") is True
    assert validate_input("CONF T", task, "Cisco") is True
    assert validate_input("wrong command", task, "Cisco") is False

def test_validate_input_linux_case_sensitive():
    task = Task(
        id="test_task",
        prompt="Print directory",
        prefix="$",
        expected="^pwd$",
        aliases=[]
    )
    # Linux platform is case-sensitive
    assert validate_input("pwd", task, "Linux") is True
    assert validate_input("PWD", task, "Linux") is False
    assert validate_input(" pwd ", task, "Linux") is True  # strip is applied

def test_validate_input_powershell_case_insensitive():
    task = Task(
        id="test_task",
        prompt="Get services",
        prefix="PS C:\\>",
        expected="^Get-Service$",
        aliases=["gsv"]
    )
    assert validate_input("get-service", task, "PowerShell") is True
    assert validate_input("GSV", task, "PowerShell") is True

def test_validate_input_fallback_exact_match():
    # Invalid expected regex falls through to aliases instead of crashing.
    task_with_alias = Task(
        id="test_task",
        prompt="Command with bad regex",
        prefix="$",
        expected="[invalid-regex",
        aliases=["exact_cmd"]
    )
    assert validate_input("exact_cmd", task_with_alias, "Linux") is True

# 2. Tests for LessonLoader
def test_lesson_loader_empty_or_nonexistent_dir(tmp_path):
    loader = LessonLoader(lessons_dir=tmp_path / "nonexistent")
    assert loader.load_all_lessons() == []

def test_lesson_loader_save_and_load(tmp_path):
    loader = LessonLoader(lessons_dir=tmp_path)
    task = Task(id="t1", prompt="Prompt 1", prefix=">", expected="^cmd1$", aliases=[], hint="h1", explanation="e1")
    lesson = Lesson(id="test_lesson", title="Test Lesson", platform="Linux", description="Desc", tasks=[task])
    
    # Save lesson
    assert loader.save_lesson(lesson) is True
    
    # Load all
    lessons = loader.load_all_lessons()
    assert len(lessons) == 1
    assert lessons[0].id == "test_lesson"
    assert lessons[0].title == "Test Lesson"
    assert len(lessons[0].tasks) == 1
    assert lessons[0].tasks[0].prompt == "Prompt 1"
    
    # Get by ID
    retrieved = loader.get_lesson_by_id("test_lesson")
    assert retrieved is not None
    assert retrieved.id == "test_lesson"
    
    # Non-existent ID
    assert loader.get_lesson_by_id("nonexistent") is None

def test_format_display_answer_prefers_alias():
    task = Task(
        id="t1",
        prompt="Enter config mode",
        prefix="Router#",
        expected="^configure\\s+terminal$",
        aliases=["conf t", "config t"],
    )
    assert format_display_answer(task, "Cisco") == "conf t"

def test_format_display_answer_strips_regex():
    task = Task(
        id="t1",
        prompt="Print directory",
        prefix="$",
        expected="^pwd$",
        aliases=[],
    )
    assert format_display_answer(task, "Linux") == "pwd"

def test_sort_lessons_by_curriculum_orders_by_difficulty():
    lessons = [
        Lesson(id="advanced", title="Advanced", platform="Linux", description="", difficulty="advanced", tasks=[]),
        Lesson(id="beginner", title="Basics", platform="Linux", description="", difficulty="beginner", tasks=[]),
        Lesson(id="intermediate", title="Middle", platform="Linux", description="", difficulty="intermediate", tasks=[]),
    ]
    ordered = sort_lessons_by_curriculum(lessons)
    assert [lesson.id for lesson in ordered] == ["beginner", "intermediate", "advanced"]


def test_parse_tags_csv():
    assert parse_tags_csv(None) == []
    assert parse_tags_csv("") == []
    assert parse_tags_csv("vlan, ospf, CCNA") == ["vlan", "ospf", "ccna"]


def test_filter_lessons_by_tags():
    lessons = [
        Lesson(
            id="vlan",
            title="VLAN",
            platform="Cisco",
            description="",
            tags=["vlan", "switching"],
            tasks=[],
        ),
        Lesson(
            id="ospf",
            title="OSPF",
            platform="Cisco",
            description="",
            tags=["ospf", "routing"],
            tasks=[],
        ),
    ]
    assert [lesson.id for lesson in filter_lessons_by_tags(lessons, ["vlan"])] == ["vlan"]
    assert [lesson.id for lesson in filter_lessons_by_tags(lessons, ["routing"])] == ["ospf"]
    assert len(filter_lessons_by_tags(lessons, ["vlan", "routing"])) == 0
    assert lesson_matches_tags(lessons[0], ["vlan", "switching"]) is True


def test_collect_all_tags():
    lessons = [
        Lesson(id="a", title="A", platform="Cisco", description="", tags=["vlan", "ccna"], tasks=[]),
        Lesson(id="b", title="B", platform="Cisco", description="", tags=["ospf", "ccna"], tasks=[]),
    ]
    assert collect_all_tags(lessons) == ["ccna", "ospf", "vlan"]
