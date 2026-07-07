import { describe, it, expect } from "vitest";
import { validateInput, formatDisplayAnswer } from "./validate";
import type { Task } from "./types";

const ciscoTask: Task = {
  id: "test_task",
  prompt: "Enter config mode",
  prefix: "Router#",
  expected: "^configure\\s+terminal$",
  aliases: ["conf t", "config t"],
  hint: "",
  explanation: "",
};

describe("validateInput", () => {
  it("is case-insensitive for Cisco", () => {
    expect(validateInput("configure terminal", ciscoTask, "Cisco")).toBe(true);
    expect(validateInput("CONFIGURE TERMINAL", ciscoTask, "Cisco")).toBe(true);
    expect(validateInput("conf t", ciscoTask, "Cisco")).toBe(true);
    expect(validateInput("CONF T", ciscoTask, "Cisco")).toBe(true);
    expect(validateInput("wrong command", ciscoTask, "Cisco")).toBe(false);
  });

  it("is case-sensitive for Linux", () => {
    const task: Task = {
      id: "test_task",
      prompt: "Print directory",
      prefix: "$",
      expected: "^pwd$",
      aliases: [],
      hint: "",
      explanation: "",
    };
    expect(validateInput("pwd", task, "Linux")).toBe(true);
    expect(validateInput("PWD", task, "Linux")).toBe(false);
    expect(validateInput(" pwd ", task, "Linux")).toBe(true);
  });

  it("is case-insensitive for PowerShell", () => {
    const task: Task = {
      id: "test_task",
      prompt: "Get services",
      prefix: "PS C:\\>",
      expected: "^Get-Service$",
      aliases: ["gsv"],
      hint: "",
      explanation: "",
    };
    expect(validateInput("get-service", task, "PowerShell")).toBe(true);
    expect(validateInput("GSV", task, "PowerShell")).toBe(true);
  });

  it("falls back to aliases when expected regex is invalid", () => {
    const task: Task = {
      id: "test_task",
      prompt: "Command with bad regex",
      prefix: "$",
      expected: "[invalid-regex",
      aliases: ["exact_cmd"],
      hint: "",
      explanation: "",
    };
    expect(validateInput("exact_cmd", task, "Linux")).toBe(true);
  });
});

describe("formatDisplayAnswer", () => {
  it("returns first alias when present", () => {
    expect(formatDisplayAnswer(ciscoTask, "Cisco")).toBe("conf t");
  });

  it("strips regex anchors and escapes when no aliases", () => {
    const task: Task = {
      id: "t1",
      prompt: "Print directory",
      prefix: "$",
      expected: "^pwd$",
      aliases: [],
      hint: "",
      explanation: "",
    };
    expect(formatDisplayAnswer(task, "Linux")).toBe("pwd");
  });
});