import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated coverage report (Istanbul's own JS) — lints dirty otherwise.
    "coverage/**",
    // Vendored shadcn CLI output (Story 2.1, AC 12) — regenerable, never
    // hand-edited, excluded from our lint expectations.
    "components/ui/**",
    "hooks/use-mobile.ts",
    "lib/utils.ts",
  ]),
]);

export default eslintConfig;
