import { cpSync, mkdirSync, readdirSync, readFileSync, writeFileSync, rmSync } from "fs";
import { join, resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { execSync } from "child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "../..");
const srcDir = join(repoRoot, "conf_t/lessons");
const destDir = join(__dirname, "../public/lessons");

rmSync(destDir, { recursive: true, force: true });
mkdirSync(destDir, { recursive: true });

execSync("pytest tests/test_lessons.py -q", { cwd: repoRoot, stdio: "inherit" });

const files = readdirSync(srcDir).filter((f) => f.endsWith(".json"));
const index = [];

for (const file of files) {
  cpSync(join(srcDir, file), join(destDir, file));
  const lesson = JSON.parse(readFileSync(join(srcDir, file), "utf-8"));
  index.push({
    id: lesson.id,
    title: lesson.title,
    platform: lesson.platform,
    description: lesson.description,
    difficulty: lesson.difficulty ?? "beginner",
    tags: lesson.tags ?? [],
    prerequisites: lesson.prerequisites ?? [],
    estimated_minutes: lesson.estimated_minutes ?? 0,
    task_count: (lesson.tasks ?? []).length,
  });
}

index.sort((a, b) => a.title.localeCompare(b.title));
writeFileSync(join(__dirname, "../public/lessons-index.json"), JSON.stringify(index, null, 2));
console.log(`Synced ${files.length} lessons`);