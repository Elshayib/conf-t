import type { Task } from "./types";

export function validateInput(
  userInput: string,
  task: Task,
  platform: string
): boolean {
  const cleanedInput = userInput.trim();
  const isCaseInsensitive = ["cisco", "powershell"].includes(
    platform.toLowerCase()
  );
  const flags = isCaseInsensitive ? "i" : "";

  try {
    const pattern = new RegExp(task.expected, flags);
    if (pattern.exec(cleanedInput)) {
      return true;
    }
  } catch {
    // invalid regex — fall through to aliases
  }

  for (const alias of task.aliases) {
    const aliasClean = alias.trim();
    if (isCaseInsensitive) {
      if (cleanedInput.toLowerCase() === aliasClean.toLowerCase()) {
        return true;
      }
    } else {
      if (cleanedInput === aliasClean) {
        return true;
      }
    }
  }

  return false;
}

export function formatDisplayAnswer(task: Task, _platform: string): string {
  if (task.aliases.length > 0) {
    return task.aliases[0];
  }

  let display = task.expected;
  if (display.startsWith("^")) {
    display = display.slice(1);
  }
  if (display.endsWith("$")) {
    display = display.slice(0, -1);
  }
  display = display.replace("\\s+", " ");
  display = display.replace("\\s", " ");
  display = display.replace("\\", "");
  return display;
}