import type { KeyStatusView } from "@/lib/api-types"

export const mockKeyStatus: KeyStatusView = {
  overall: "has-keys",
  key_config_path: "/path/to/key-config.yaml",
  providers: [
    {
      name: "anthropic",
      status: "available",
      detail: "API key found",
      usable: true,
      env_var: "ANTHROPIC_API_KEY",
      fix_hint: null,
      credential_source: "key-config",
    },
    {
      name: "openrouter",
      status: "available",
      detail: "API key found",
      usable: true,
      env_var: "OPENROUTER_API_KEY",
      fix_hint: null,
      credential_source: "key-config",
    },
    {
      name: "openai",
      status: "missing",
      detail: "API key not found",
      usable: false,
      env_var: "OPENAI_API_KEY",
      fix_hint: "Add OPENAI_API_KEY to your Key Config",
      credential_source: "none",
    },
    {
      name: "ollama",
      status: "keyless-local",
      detail: "Local provider, no key required",
      usable: true,
      env_var: null,
      fix_hint: null,
      credential_source: "none",
    },
  ],
  load_warnings: [],
  any_key_present: true,
  needs_restart_to_author: [],
}

export const mockNoKeysStatus: KeyStatusView = {
  overall: "no-keys",
  key_config_path: "/path/to/key-config.yaml",
  providers: [
    {
      name: "ollama",
      status: "keyless-local",
      detail: "Local provider, no key required",
      usable: true,
      env_var: null,
      fix_hint: null,
      credential_source: "none",
    },
  ],
  load_warnings: [],
  any_key_present: false,
  needs_restart_to_author: [],
}

export const mockWithWarnings: KeyStatusView = {
  overall: "has-keys",
  key_config_path: "/path/to/key-config.yaml",
  providers: [
    {
      name: "anthropic",
      status: "available",
      detail: "API key found",
      usable: true,
      env_var: "ANTHROPIC_API_KEY",
      fix_hint: null,
      credential_source: "key-config",
    },
  ],
  load_warnings: ["Key Config file permissions are too open"],
  any_key_present: true,
  needs_restart_to_author: [],
}

export const mockNeedsRestart: KeyStatusView = {
  overall: "has-keys",
  key_config_path: "/path/to/key-config.yaml",
  providers: [
    {
      name: "anthropic",
      status: "available",
      detail: "API key found",
      usable: true,
      env_var: "ANTHROPIC_API_KEY",
      fix_hint: null,
      credential_source: "key-config",
    },
  ],
  load_warnings: [],
  any_key_present: true,
  needs_restart_to_author: ["anthropic"],
}

export const mockNeedsRestartMultiple: KeyStatusView = {
  overall: "has-keys",
  key_config_path: "/path/to/key-config.yaml",
  providers: [
    {
      name: "anthropic",
      status: "available",
      detail: "API key found",
      usable: true,
      env_var: "ANTHROPIC_API_KEY",
      fix_hint: null,
      credential_source: "key-config",
    },
  ],
  load_warnings: [],
  any_key_present: true,
  needs_restart_to_author: ["anthropic", "openai"],
}
