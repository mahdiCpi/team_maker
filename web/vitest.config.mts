import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { coverageConfigDefaults, defineConfig } from "vitest/config";

// Not `import.meta.dirname`: that landed in Node 20.11, but the project's
// documented floor is Node 20.9 (Next 16's requirement). On 20.9/20.10 it is
// undefined and path.resolve throws while Vitest is still loading its config.
const rootDir = path.dirname(fileURLToPath(import.meta.url));

/** Vendored shadcn CLI output — regenerable, never hand-edited (AC 12). */
const VENDORED = [
  "components/ui/**",
  "hooks/use-mobile.ts",
  "lib/utils.ts",
];

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
    css: true,
    coverage: {
      provider: "v8",
      // Without an explicit include, v8 reports only files the tests import,
      // which produced a near-perfect number covering a single helper.
      include: ["app/**", "components/**", "lib/**", "hooks/**"],
      // Spread the defaults: assigning `exclude` REPLACES them, which drops
      // node_modules, dist and *.d.ts from the exclusion list.
      exclude: [...coverageConfigDefaults.exclude, ...VENDORED, "**/*.config.*"],
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "."),
    },
  },
});
