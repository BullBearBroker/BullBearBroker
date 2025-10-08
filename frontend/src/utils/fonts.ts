type InterFactory = typeof import("next/font/google").Inter;

export const inter = (() => {
  try {
    const { Inter } = require("next/font/google") as { Inter?: InterFactory };
    if (typeof Inter === "function") {
      return Inter({
        subsets: ["latin"],
        display: "swap",
      });
    }
    throw new Error("next/font/google not available");
  } catch {
    return { className: "font-inter-fallback" };
  }
})();
