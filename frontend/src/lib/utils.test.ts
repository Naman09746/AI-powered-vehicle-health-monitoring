import { describe, it, expect } from "vitest";
import { cn, formatNumber, formatTimestamp, getFailureColor, getHealthColor } from "./utils";

describe("cn", () => {
  it("merges class names", () => { expect(cn("a", "b")).toBe("a b"); });
  it("handles conditional classes", () => { expect(cn("a", false && "b", "c")).toBe("a c"); });
  it("resolves tailwind conflicts", () => { expect(cn("px-2", "px-4")).toBe("px-4"); });
});

describe("formatNumber", () => {
  it("formats with default decimals", () => { expect(formatNumber(3.456)).toBe("3.5"); });
  it("formats with custom decimals", () => { expect(formatNumber(3.456, 2)).toBe("3.46"); });
  it("handles integers", () => { expect(formatNumber(42)).toBe("42.0"); });
});

describe("formatTimestamp", () => {
  it("formats date string", () => {
    const r = formatTimestamp("2026-07-14T12:00:00Z");
    expect(r).toContain("Jul");
  });
});

describe("getFailureColor", () => {
  it("returns green for low risk", () => { expect(getFailureColor(0.3)).toBe("#10b981"); });
  it("returns amber for medium risk", () => { expect(getFailureColor(0.5)).toBe("#f59e0b"); });
  it("returns red for high risk", () => { expect(getFailureColor(0.8)).toBe("#ef4444"); });
});

describe("getHealthColor", () => {
  it("returns green for excellent", () => { expect(getHealthColor(96)).toBe("#10b981"); });
  it("returns blue for good", () => { expect(getHealthColor(85)).toBe("#0ea5e9"); });
  it("returns amber for warning", () => { expect(getHealthColor(70)).toBe("#f59e0b"); });
  it("returns red for critical", () => { expect(getHealthColor(40)).toBe("#ef4444"); });
});
