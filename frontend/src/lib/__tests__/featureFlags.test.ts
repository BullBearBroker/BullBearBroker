import { __resetFeatureFlagsForTests, getFeatureFlag } from "../featureFlags";

describe("feature flags utility", () => {
  beforeEach(() => {
    __resetFeatureFlagsForTests();
    delete process.env.NEXT_PUBLIC_FEATURE_FLAGS;
  });

  it("interprets JSON arrays", () => {
    process.env.NEXT_PUBLIC_FEATURE_FLAGS = JSON.stringify(["portfolio-csv", "beta"]);
    expect(getFeatureFlag("portfolio-csv")).toBe(true);
    expect(getFeatureFlag("missing")).toBe(false);
  });

  it("interprets JSON objects with various truthy values", () => {
    process.env.NEXT_PUBLIC_FEATURE_FLAGS = JSON.stringify({
      "portfolio-csv": true,
      other: "true",
      disabled: false,
    });
    expect(getFeatureFlag("portfolio-csv")).toBe(true);
    expect(getFeatureFlag("other")).toBe(true);
    expect(getFeatureFlag("disabled")).toBe(false);
  });

  it("falls back to comma separated strings", () => {
    process.env.NEXT_PUBLIC_FEATURE_FLAGS = "portfolio-csv, another";
    expect(getFeatureFlag("portfolio-csv")).toBe(true);
    expect(getFeatureFlag("another")).toBe(true);
    expect(getFeatureFlag("absent")).toBe(false);
  });
});
