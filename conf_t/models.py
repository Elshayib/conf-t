from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Task:
    id: str
    prompt: str
    prefix: str
    expected: str  # Regex pattern
    aliases: List[str] = field(default_factory=list)
    hint: str = ""
    explanation: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            prompt=data["prompt"],
            prefix=data["prefix"],
            expected=data["expected"],
            aliases=data.get("aliases", []),
            hint=data.get("hint", ""),
            explanation=data.get("explanation", "")
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "prefix": self.prefix,
            "expected": self.expected,
            "aliases": self.aliases,
            "hint": self.hint,
            "explanation": self.explanation
        }


@dataclass
class Lesson:
    id: str
    title: str
    platform: str
    description: str
    tasks: List[Task]
    difficulty: str = "beginner"
    tags: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    estimated_minutes: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Lesson":
        return cls(
            id=data["id"],
            title=data["title"],
            platform=data["platform"],
            description=data["description"],
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
            difficulty=data.get("difficulty", "beginner"),
            tags=data.get("tags", []),
            prerequisites=data.get("prerequisites", []),
            estimated_minutes=data.get("estimated_minutes", 0),
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "platform": self.platform,
            "description": self.description,
            "tasks": [t.to_dict() for t in self.tasks],
        }
        if self.difficulty != "beginner":
            result["difficulty"] = self.difficulty
        if self.tags:
            result["tags"] = self.tags
        if self.prerequisites:
            result["prerequisites"] = self.prerequisites
        if self.estimated_minutes:
            result["estimated_minutes"] = self.estimated_minutes
        return result


@dataclass
class SessionStats:
    total_questions: int = 0
    correct_first_try: int = 0
    total_attempts: int = 0
    skipped_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_questions": self.total_questions,
            "correct_first_try": self.correct_first_try,
            "total_attempts": self.total_attempts,
            "skipped_count": self.skipped_count
        }
