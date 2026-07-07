import { readFileSync } from "fs";
import { join } from "path";
import type { LessonIndexEntry } from "@/lib/engine/types";

export function getLessonsIndex(): LessonIndexEntry[] {
  const filePath = join(process.cwd(), "public", "lessons-index.json");
  const raw = readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as LessonIndexEntry[];
}

export function getLandingStats() {
  const lessons = getLessonsIndex();
  const taskCount = lessons.reduce((sum, entry) => sum + entry.task_count, 0);
  const platformCounts = new Map<string, number>();

  for (const lesson of lessons) {
    platformCounts.set(
      lesson.platform,
      (platformCounts.get(lesson.platform) ?? 0) + 1
    );
  }

  const platforms = [...platformCounts.entries()]
    .map(([name, lessonCount]) => ({
      name,
      slug: name.toLowerCase(),
      lessonCount,
      taskCount: lessons
        .filter((entry) => entry.platform === name)
        .reduce((sum, entry) => sum + entry.task_count, 0),
    }))
    .sort((a, b) => {
      if (a.name === "Cisco") return -1;
      if (b.name === "Cisco") return 1;
      return a.name.localeCompare(b.name);
    });

  return {
    lessonCount: lessons.length,
    taskCount,
    platformCount: platforms.length,
    platforms,
  };
}