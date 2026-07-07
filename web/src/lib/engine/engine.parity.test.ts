import { describe, it, expect } from "vitest";
import { validateInput, formatDisplayAnswer } from "./validate";
import type { Task } from "./types";
import fixtures from "./fixtures/engine-fixtures.json";

interface ValidateInputFixture {
  fn: "validate_input";
  input: string;
  task: Task;
  platform: string;
  python_result: boolean;
}

interface FormatDisplayAnswerFixture {
  fn: "format_display_answer";
  task: Task;
  platform: string;
  python_result: string;
}

type EngineFixture = ValidateInputFixture | FormatDisplayAnswerFixture;

const engineFixtures = fixtures as EngineFixture[];

describe("engine parity (Python vs TypeScript)", () => {
  for (const [index, fixture] of engineFixtures.entries()) {
    if (fixture.fn === "validate_input") {
      it(`validate_input case ${index + 1}: ${fixture.input} on ${fixture.platform}`, () => {
        const result = validateInput(fixture.input, fixture.task, fixture.platform);
        expect(result).toBe(fixture.python_result);
      });
    } else if (fixture.fn === "format_display_answer") {
      it(`format_display_answer case ${index + 1}: ${fixture.task.id} on ${fixture.platform}`, () => {
        const result = formatDisplayAnswer(fixture.task, fixture.platform);
        expect(result).toBe(fixture.python_result);
      });
    }
  }
});