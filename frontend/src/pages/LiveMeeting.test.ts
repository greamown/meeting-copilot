import { describe, expect, it } from "vitest";
import { Suggestion } from "../lib/api";
import { takeNewSuggestion } from "./LiveMeeting";

describe("automatic suggestion speech", () => {
  it("returns each new suggestion only once", () => {
    const suggestions = [
      { id: "old", status: "pending" },
      { id: "new", status: "pending" },
    ] as Suggestion[];
    const seen = new Set(["old"]);
    expect(takeNewSuggestion(suggestions, seen)?.id).toBe("new");
    expect(takeNewSuggestion(suggestions, seen)).toBeUndefined();
  });
});
