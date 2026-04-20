import type { GatewayBrowserClient } from "../gateway.ts";
import type { SkillStatusReport } from "../types.ts";

export type JunoHubSearchResult = {
  score: number;
  slug: string;
  displayName: string;
  summary?: string;
  version?: string;
  updatedAt?: number;
};

export type JunoHubSkillDetail = {
  skill: {
    slug: string;
    displayName: string;
    summary?: string;
    tags?: Record<string, string>;
    createdAt: number;
    updatedAt: number;
  } | null;
  latestVersion?: {
    version: string;
    createdAt: number;
    changelog?: string;
  } | null;
  metadata?: {
    os?: string[] | null;
    systems?: string[] | null;
  } | null;
  owner?: {
    handle?: string | null;
    displayName?: string | null;
    image?: string | null;
  } | null;
};

export type SkillsState = {
  client: GatewayBrowserClient | null;
  connected: boolean;
  skillsLoading: boolean;
  skillsReport: SkillStatusReport | null;
  skillsError: string | null;
  skillsBusyKey: string | null;
  skillEdits: Record<string, string>;
  skillMessages: SkillMessageMap;
  junohubSearchQuery: string;
  junohubSearchResults: JunoHubSearchResult[] | null;
  junohubSearchLoading: boolean;
  junohubSearchError: string | null;
  junohubDetail: JunoHubSkillDetail | null;
  junohubDetailSlug: string | null;
  junohubDetailLoading: boolean;
  junohubDetailError: string | null;
  junohubInstallSlug: string | null;
  junohubInstallMessage: { kind: "success" | "error"; text: string } | null;
};

export type SkillMessage = {
  kind: "success" | "error";
  message: string;
};

export type SkillMessageMap = Record<string, SkillMessage>;

function setSkillMessage(state: SkillsState, key: string, message: SkillMessage) {
  if (!key.trim()) {
    return;
  }
  state.skillMessages = { ...state.skillMessages, [key]: message };
}

const getErrorMessage = (err: unknown) => (err instanceof Error ? err.message : String(err));

async function runStaleAwareRequest<T>(
  isCurrent: () => boolean,
  request: () => Promise<T>,
  onSuccess: (value: T) => void,
  onError: (err: unknown) => void,
  onFinally: () => void,
) {
  try {
    const result = await request();
    if (!isCurrent()) {
      return;
    }
    onSuccess(result);
  } catch (err) {
    if (!isCurrent()) {
      return;
    }
    onError(err);
  }
  onFinally();
}

export function setJunoHubSearchQuery(state: SkillsState, query: string) {
  state.junohubSearchQuery = query;
  state.junohubInstallMessage = null;
  state.junohubSearchResults = null;
  state.junohubSearchError = null;
  state.junohubSearchLoading = false;
}

export async function loadSkills(state: SkillsState, options?: { clearMessages?: boolean }) {
  if (options?.clearMessages && Object.keys(state.skillMessages).length > 0) {
    state.skillMessages = {};
  }
  if (!state.client || !state.connected || state.skillsLoading) {
    return;
  }
  state.skillsLoading = true;
  state.skillsError = null;
  try {
    const res = await state.client.request<SkillStatusReport | undefined>("skills.status", {});
    if (res) {
      state.skillsReport = res;
    }
  } catch (err) {
    state.skillsError = getErrorMessage(err);
  } finally {
    state.skillsLoading = false;
  }
}

export function updateSkillEdit(state: SkillsState, skillKey: string, value: string) {
  state.skillEdits = { ...state.skillEdits, [skillKey]: value };
}

async function runSkillMutation(
  state: SkillsState,
  skillKey: string,
  run: (client: GatewayBrowserClient) => Promise<SkillMessage>,
) {
  const client = state.client;
  if (!client || !state.connected) {
    return;
  }
  state.skillsBusyKey = skillKey;
  state.skillsError = null;
  try {
    const message = await run(client);
    await loadSkills(state);
    setSkillMessage(state, skillKey, message);
  } catch (err) {
    const message = getErrorMessage(err);
    state.skillsError = message;
    setSkillMessage(state, skillKey, {
      kind: "error",
      message,
    });
  } finally {
    state.skillsBusyKey = null;
  }
}

export async function updateSkillEnabled(state: SkillsState, skillKey: string, enabled: boolean) {
  await runSkillMutation(state, skillKey, async (client) => {
    await client.request("skills.update", { skillKey, enabled });
    return {
      kind: "success",
      message: enabled ? "Skill enabled" : "Skill disabled",
    };
  });
}

export async function saveSkillApiKey(state: SkillsState, skillKey: string) {
  await runSkillMutation(state, skillKey, async (client) => {
    const apiKey = state.skillEdits[skillKey] ?? "";
    await client.request("skills.update", { skillKey, apiKey });
    return {
      kind: "success",
      message: `API key saved — stored in juno.json (skills.entries.${skillKey})`,
    };
  });
}

export async function installSkill(
  state: SkillsState,
  skillKey: string,
  name: string,
  installId: string,
  dangerouslyForceUnsafeInstall = false,
) {
  await runSkillMutation(state, skillKey, async (client) => {
    const result = await client.request<{ message?: string }>("skills.install", {
      name,
      installId,
      dangerouslyForceUnsafeInstall,
      timeoutMs: 120000,
    });
    return {
      kind: "success",
      message: result?.message ?? "Installed",
    };
  });
}

export async function searchJunoHub(state: SkillsState, query: string) {
  if (!state.client || !state.connected) {
    return;
  }
  if (!query.trim()) {
    state.junohubSearchResults = null;
    state.junohubSearchError = null;
    state.junohubSearchLoading = false;
    return;
  }
  const client = state.client;
  // Clear stale entries as soon as a new search begins so the UI cannot act on
  // results that no longer match the current query while the next request is in flight.
  state.junohubSearchResults = null;
  state.junohubSearchLoading = true;
  state.junohubSearchError = null;
  await runStaleAwareRequest(
    () => query === state.junohubSearchQuery,
    () =>
      client.request<{ results: JunoHubSearchResult[] }>("skills.search", {
        query,
        limit: 20,
      }),
    (res) => {
      state.junohubSearchResults = res?.results ?? [];
    },
    (err) => {
      state.junohubSearchError = getErrorMessage(err);
    },
    () => {
      state.junohubSearchLoading = false;
    },
  );
}

export async function loadJunoHubDetail(state: SkillsState, slug: string) {
  if (!state.client || !state.connected) {
    return;
  }
  const client = state.client;
  state.junohubDetailSlug = slug;
  state.junohubDetailLoading = true;
  state.junohubDetailError = null;
  state.junohubDetail = null;
  await runStaleAwareRequest(
    () => slug === state.junohubDetailSlug,
    () => client.request<JunoHubSkillDetail>("skills.detail", { slug }),
    (res) => {
      state.junohubDetail = res ?? null;
    },
    (err) => {
      state.junohubDetailError = getErrorMessage(err);
    },
    () => {
      state.junohubDetailLoading = false;
    },
  );
}

export function closeJunoHubDetail(state: SkillsState) {
  state.junohubDetailSlug = null;
  state.junohubDetail = null;
  state.junohubDetailError = null;
  state.junohubDetailLoading = false;
}

export async function installFromJunoHub(state: SkillsState, slug: string) {
  if (!state.client || !state.connected) {
    return;
  }
  state.junohubInstallSlug = slug;
  state.junohubInstallMessage = null;
  try {
    await state.client.request("skills.install", { source: "junohub", slug });
    await loadSkills(state);
    state.junohubInstallMessage = { kind: "success", text: `Installed ${slug}` };
  } catch (err) {
    state.junohubInstallMessage = { kind: "error", text: getErrorMessage(err) };
  } finally {
    state.junohubInstallSlug = null;
  }
}
