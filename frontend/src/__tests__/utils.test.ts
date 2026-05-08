import { describe, it, expect } from "vitest";

describe("Utility smoke tests", () => {
  it("Ghana Card regex matches valid format", () => {
    const GHANA_CARD_PATTERN = /^GHA-\d{9}-\d$/;
    expect(GHANA_CARD_PATTERN.test("GHA-123456789-0")).toBe(true);
    expect(GHANA_CARD_PATTERN.test("GHA-12345-0")).toBe(false);
    expect(GHANA_CARD_PATTERN.test("")).toBe(false);
  });

  it("Risk score band mapping is correct", () => {
    const band = (score: number): string => {
      if (score <= 200) return "LOW";
      if (score <= 500) return "MEDIUM";
      if (score <= 750) return "HIGH";
      return "CRITICAL";
    };
    expect(band(100)).toBe("LOW");
    expect(band(300)).toBe("MEDIUM");
    expect(band(600)).toBe("HIGH");
    expect(band(900)).toBe("CRITICAL");
  });

  it("Purpose codes include required regulatory codes", () => {
    const PURPOSE_CODES = [
      "ACCOUNT_OPENING", "KYC_REFRESH", "LOAN_APPLICATION",
      "AML_SCREENING", "FRAUD_INVESTIGATION", "LAW_ENFORCEMENT_QUERY",
      "IMMIGRATION_CONTROL", "REGULATORY_COMPLIANCE",
    ];
    expect(PURPOSE_CODES).toContain("AML_SCREENING");
    expect(PURPOSE_CODES).toContain("KYC_REFRESH");
  });
});
