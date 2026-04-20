import { createHash } from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {
  normalizeLowercaseStringOrEmpty,
  normalizeOptionalString,
} from "../shared/string-coerce.js";
import { isAtLeast, parseSemver } from "./runtime-guard.js";
import { compareComparableSemver, parseComparableSemver } from "./semver-compare.js";
import { createTempDownloadTarget } from "./temp-download.js";
export { parseJunoHubPluginSpec } from "./junohub-spec.js";

const DEFAULT_JUNOHUB_URL = "https://junohub.ai";
const DEFAULT_FETCH_TIMEOUT_MS = 30_000;

export type JunoHubPackageFamily = "skill" | "code-plugin" | "bundle-plugin";
export type JunoHubPackageChannel = "official" | "community" | "private";
// Keep aligned with @juno/plugin-package-contract ExternalPluginCompatibility.
export type JunoHubPackageCompatibility = {
  pluginApiRange?: string;
  builtWithJunoVersion?: string;
  pluginSdkVersion?: string;
  minGatewayVersion?: string;
};
export type JunoHubPackageListItem = {
  name: string;
  displayName: string;
  family: JunoHubPackageFamily;
  runtimeId?: string | null;
  channel: JunoHubPackageChannel;
  isOfficial: boolean;
  summary?: string | null;
  ownerHandle?: string | null;
  createdAt: number;
  updatedAt: number;
  latestVersion?: string | null;
  capabilityTags?: string[];
  executesCode?: boolean;
  verificationTier?: string | null;
};
export type JunoHubPackageDetail = {
  package:
    | (JunoHubPackageListItem & {
        tags?: Record<string, string>;
        compatibility?: JunoHubPackageCompatibility | null;
        capabilities?: {
          executesCode?: boolean;
          runtimeId?: string;
          capabilityTags?: string[];
          bundleFormat?: string;
          hostTargets?: string[];
          pluginKind?: string;
          channels?: string[];
          providers?: string[];
          hooks?: string[];
          bundledSkills?: string[];
        } | null;
        verification?: {
          tier?: string;
          scope?: string;
          summary?: string;
          sourceRepo?: string;
          sourceCommit?: string;
          hasProvenance?: boolean;
          scanStatus?: string;
        } | null;
      })
    | null;
  owner?: {
    handle?: string | null;
    displayName?: string | null;
    image?: string | null;
  } | null;
};

export type JunoHubPackageVersion = {
  package: {
    name: string;
    displayName: string;
    family: JunoHubPackageFamily;
  } | null;
  version: {
    version: string;
    createdAt: number;
    changelog: string;
    distTags?: string[];
    files?: Array<{
      path: string;
      size: number;
      sha256: string;
      contentType?: string;
    }>;
    sha256hash?: string | null;
    compatibility?: JunoHubPackageCompatibility | null;
    capabilities?: JunoHubPackageDetail["package"] extends infer T
      ? T extends { capabilities?: infer C }
        ? C
        : never
      : never;
    verification?: JunoHubPackageDetail["package"] extends infer T
      ? T extends { verification?: infer C }
        ? C
        : never
      : never;
  } | null;
};

export type JunoHubPackageSearchResult = {
  score: number;
  package: JunoHubPackageListItem;
};

export type JunoHubSkillSearchResult = {
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

export type JunoHubSkillListResponse = {
  items: Array<{
    slug: string;
    displayName: string;
    summary?: string;
    tags?: Record<string, string>;
    latestVersion?: {
      version: string;
      createdAt: number;
      changelog?: string;
    } | null;
    metadata?: {
      os?: string[] | null;
      systems?: string[] | null;
    } | null;
    createdAt: number;
    updatedAt: number;
  }>;
  nextCursor?: string | null;
};

export type JunoHubDownloadResult = {
  archivePath: string;
  integrity: string;
  cleanup: () => Promise<void>;
};

type FetchLike = (input: string | URL | Request, init?: RequestInit) => Promise<Response>;

type JunoHubRequestParams = {
  baseUrl?: string;
  path: string;
  token?: string;
  timeoutMs?: number;
  search?: Record<string, string | undefined>;
  fetchImpl?: FetchLike;
};

type JunoHubConfigLike = {
  token?: unknown;
  accessToken?: unknown;
  authToken?: unknown;
  apiToken?: unknown;
  auth?: JunoHubConfigLike | null;
  session?: JunoHubConfigLike | null;
  credentials?: JunoHubConfigLike | null;
  user?: JunoHubConfigLike | null;
};

export class JunoHubRequestError extends Error {
  readonly status: number;
  readonly requestPath: string;
  readonly responseBody: string;

  constructor(params: { path: string; status: number; body: string }) {
    super(`JunoHub ${params.path} failed (${params.status}): ${params.body}`);
    this.name = "JunoHubRequestError";
    this.status = params.status;
    this.requestPath = params.path;
    this.responseBody = params.body;
  }
}

function normalizeBaseUrl(baseUrl?: string): string {
  const envValue =
    normalizeOptionalString(process.env.JUNO_JUNOHUB_URL) ||
    normalizeOptionalString(process.env.JUNOHUB_URL) ||
    DEFAULT_JUNOHUB_URL;
  const value = (normalizeOptionalString(baseUrl) || envValue).replace(/\/+$/, "");
  return value || DEFAULT_JUNOHUB_URL;
}

function extractTokenFromJunoHubConfig(value: unknown): string | undefined {
  if (!value || typeof value !== "object") {
    return undefined;
  }
  const record = value as JunoHubConfigLike;
  return (
    normalizeOptionalString(record.accessToken) ??
    normalizeOptionalString(record.authToken) ??
    normalizeOptionalString(record.apiToken) ??
    normalizeOptionalString(record.token) ??
    extractTokenFromJunoHubConfig(record.auth) ??
    extractTokenFromJunoHubConfig(record.session) ??
    extractTokenFromJunoHubConfig(record.credentials) ??
    extractTokenFromJunoHubConfig(record.user)
  );
}

function resolveJunoHubConfigPaths(): string[] {
  const explicit =
    normalizeOptionalString(process.env.JUNO_JUNOHUB_CONFIG_PATH) ||
    normalizeOptionalString(process.env.JUNOHUB_CONFIG_PATH) ||
    normalizeOptionalString(process.env.JUNODHUB_CONFIG_PATH); // legacy misspelling from older junohub CLI builds; keep for back-compat
  if (explicit) {
    return [explicit];
  }

  const xdgConfigHome = normalizeOptionalString(process.env.XDG_CONFIG_HOME);
  const configHome =
    xdgConfigHome && xdgConfigHome.length > 0 ? xdgConfigHome : path.join(os.homedir(), ".config");
  const xdgPath = path.join(configHome, "junohub", "config.json");

  if (process.platform === "darwin") {
    return [
      path.join(os.homedir(), "Library", "Application Support", "junohub", "config.json"),
      xdgPath,
    ];
  }

  return [xdgPath];
}

export async function resolveJunoHubAuthToken(): Promise<string | undefined> {
  const envToken =
    normalizeOptionalString(process.env.JUNO_JUNOHUB_TOKEN) ||
    normalizeOptionalString(process.env.JUNOHUB_TOKEN) ||
    normalizeOptionalString(process.env.JUNOHUB_AUTH_TOKEN);
  if (envToken) {
    return envToken;
  }

  for (const configPath of resolveJunoHubConfigPaths()) {
    try {
      const raw = await fs.readFile(configPath, "utf8");
      const token = extractTokenFromJunoHubConfig(JSON.parse(raw));
      if (token) {
        return token;
      }
    } catch {
      // Try the next candidate path.
    }
  }
  return undefined;
}

function compareSemver(left: string, right: string): number | null {
  return compareComparableSemver(parseComparableSemver(left), parseComparableSemver(right));
}

function upperBoundForCaret(version: string): string | null {
  const parsed = parseComparableSemver(version);
  if (!parsed) {
    return null;
  }
  if (parsed.major > 0) {
    return `${parsed.major + 1}.0.0`;
  }
  if (parsed.minor > 0) {
    return `0.${parsed.minor + 1}.0`;
  }
  return `0.0.${parsed.patch + 1}`;
}

function satisfiesComparator(version: string, token: string): boolean {
  const trimmed = token.trim();
  if (!trimmed) {
    return true;
  }
  if (trimmed.startsWith("^")) {
    const base = trimmed.slice(1).trim();
    const upperBound = upperBoundForCaret(base);
    const lowerCmp = compareSemver(version, base);
    const upperCmp = upperBound ? compareSemver(version, upperBound) : null;
    return lowerCmp != null && upperCmp != null && lowerCmp >= 0 && upperCmp < 0;
  }

  const match = /^(>=|<=|>|<|=)?\s*(.+)$/.exec(trimmed);
  if (!match) {
    return false;
  }
  const operator = match[1] ?? "=";
  const target = match[2]?.trim();
  if (!target) {
    return false;
  }
  const cmp = compareSemver(version, target);
  if (cmp == null) {
    return false;
  }
  switch (operator) {
    case ">=":
      return cmp >= 0;
    case "<=":
      return cmp <= 0;
    case ">":
      return cmp > 0;
    case "<":
      return cmp < 0;
    case "=":
    default:
      return cmp === 0;
  }
}

function satisfiesSemverRange(version: string, range: string): boolean {
  const tokens = range
    .trim()
    .split(/\s+/)
    .map((token) => token.trim())
    .filter(Boolean);
  if (tokens.length === 0) {
    return false;
  }
  return tokens.every((token) => satisfiesComparator(version, token));
}

function buildUrl(params: Pick<JunoHubRequestParams, "baseUrl" | "path" | "search">): URL {
  const url = new URL(params.path, `${normalizeBaseUrl(params.baseUrl)}/`);
  for (const [key, value] of Object.entries(params.search ?? {})) {
    if (!value) {
      continue;
    }
    url.searchParams.set(key, value);
  }
  return url;
}

async function junohubRequest(
  params: JunoHubRequestParams,
): Promise<{ response: Response; url: URL }> {
  const url = buildUrl(params);
  const token = normalizeOptionalString(params.token) || (await resolveJunoHubAuthToken());
  const controller = new AbortController();
  const timeout = setTimeout(
    () =>
      controller.abort(
        new Error(
          `JunoHub request timed out after ${params.timeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS}ms`,
        ),
      ),
    params.timeoutMs ?? DEFAULT_FETCH_TIMEOUT_MS,
  );
  try {
    const response = await (params.fetchImpl ?? fetch)(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      signal: controller.signal,
    });
    return { response, url };
  } finally {
    clearTimeout(timeout);
  }
}

async function readErrorBody(response: Response): Promise<string> {
  try {
    const text = (await response.text()).trim();
    return text || response.statusText || `HTTP ${response.status}`;
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}

async function fetchJson<T>(params: JunoHubRequestParams): Promise<T> {
  const { response, url } = await junohubRequest(params);
  if (!response.ok) {
    throw new JunoHubRequestError({
      path: url.pathname,
      status: response.status,
      body: await readErrorBody(response),
    });
  }
  return (await response.json()) as T;
}

export function resolveJunoHubBaseUrl(baseUrl?: string): string {
  return normalizeBaseUrl(baseUrl);
}

export function formatSha256Integrity(bytes: Uint8Array): string {
  const digest = createHash("sha256").update(bytes).digest("base64");
  return `sha256-${digest}`;
}

export function normalizeJunoHubSha256Integrity(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const prefixedBase64 = /^sha256-([A-Za-z0-9+/]+={0,1})$/.exec(trimmed);
  if (prefixedBase64?.[1]) {
    try {
      const decoded = Buffer.from(prefixedBase64[1], "base64");
      if (decoded.length === 32) {
        return `sha256-${decoded.toString("base64")}`;
      }
    } catch {
      return null;
    }
    return null;
  }
  const prefixedHex = /^sha256:([A-Fa-f0-9]{64})$/.exec(trimmed);
  if (prefixedHex?.[1]) {
    return `sha256-${Buffer.from(prefixedHex[1], "hex").toString("base64")}`;
  }
  if (/^[A-Fa-f0-9]{64}$/.test(trimmed)) {
    return `sha256-${Buffer.from(trimmed, "hex").toString("base64")}`;
  }
  return null;
}

export function normalizeJunoHubSha256Hex(value: string): string | null {
  const trimmed = value.trim();
  if (!/^[A-Fa-f0-9]{64}$/.test(trimmed)) {
    return null;
  }
  return normalizeLowercaseStringOrEmpty(trimmed);
}

export async function fetchJunoHubPackageDetail(params: {
  name: string;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}): Promise<JunoHubPackageDetail> {
  return await fetchJson<JunoHubPackageDetail>({
    baseUrl: params.baseUrl,
    path: `/api/v1/packages/${encodeURIComponent(params.name)}`,
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
  });
}

export async function fetchJunoHubPackageVersion(params: {
  name: string;
  version: string;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}): Promise<JunoHubPackageVersion> {
  return await fetchJson<JunoHubPackageVersion>({
    baseUrl: params.baseUrl,
    path: `/api/v1/packages/${encodeURIComponent(params.name)}/versions/${encodeURIComponent(
      params.version,
    )}`,
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
  });
}

export async function searchJunoHubPackages(params: {
  query: string;
  family?: JunoHubPackageFamily;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
  limit?: number;
}): Promise<JunoHubPackageSearchResult[]> {
  const result = await fetchJson<{ results: JunoHubPackageSearchResult[] }>({
    baseUrl: params.baseUrl,
    path: "/api/v1/packages/search",
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
    search: {
      q: params.query.trim(),
      family: params.family,
      limit: params.limit ? String(params.limit) : undefined,
    },
  });
  return result.results ?? [];
}

export async function searchJunoHubSkills(params: {
  query: string;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
  limit?: number;
}): Promise<JunoHubSkillSearchResult[]> {
  const result = await fetchJson<{ results: JunoHubSkillSearchResult[] }>({
    baseUrl: params.baseUrl,
    path: "/api/v1/search",
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
    search: {
      q: params.query.trim(),
      limit: params.limit ? String(params.limit) : undefined,
    },
  });
  return result.results ?? [];
}

export async function fetchJunoHubSkillDetail(params: {
  slug: string;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}): Promise<JunoHubSkillDetail> {
  return await fetchJson<JunoHubSkillDetail>({
    baseUrl: params.baseUrl,
    path: `/api/v1/skills/${encodeURIComponent(params.slug)}`,
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
  });
}

export async function listJunoHubSkills(params: {
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
  limit?: number;
}): Promise<JunoHubSkillListResponse> {
  return await fetchJson<JunoHubSkillListResponse>({
    baseUrl: params.baseUrl,
    path: "/api/v1/skills",
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
    search: {
      limit: params.limit ? String(params.limit) : undefined,
    },
  });
}

export async function downloadJunoHubPackageArchive(params: {
  name: string;
  version?: string;
  tag?: string;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}): Promise<JunoHubDownloadResult> {
  const search = params.version
    ? { version: params.version }
    : params.tag
      ? { tag: params.tag }
      : undefined;
  const { response, url } = await junohubRequest({
    baseUrl: params.baseUrl,
    path: `/api/v1/packages/${encodeURIComponent(params.name)}/download`,
    search,
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
  });
  if (!response.ok) {
    throw new JunoHubRequestError({
      path: url.pathname,
      status: response.status,
      body: await readErrorBody(response),
    });
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  const target = await createTempDownloadTarget({
    prefix: "juno-junohub-package",
    fileName: `${params.name}.zip`,
    tmpDir: os.tmpdir(),
  });
  await fs.writeFile(target.path, bytes);
  return {
    archivePath: target.path,
    integrity: formatSha256Integrity(bytes),
    cleanup: target.cleanup,
  };
}

export async function downloadJunoHubSkillArchive(params: {
  slug: string;
  version?: string;
  tag?: string;
  baseUrl?: string;
  token?: string;
  timeoutMs?: number;
  fetchImpl?: FetchLike;
}): Promise<JunoHubDownloadResult> {
  const { response, url } = await junohubRequest({
    baseUrl: params.baseUrl,
    path: "/api/v1/download",
    token: params.token,
    timeoutMs: params.timeoutMs,
    fetchImpl: params.fetchImpl,
    search: {
      slug: params.slug,
      version: params.version,
      tag: params.version ? undefined : params.tag,
    },
  });
  if (!response.ok) {
    throw new JunoHubRequestError({
      path: url.pathname,
      status: response.status,
      body: await readErrorBody(response),
    });
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  const target = await createTempDownloadTarget({
    prefix: "juno-junohub-skill",
    fileName: `${params.slug}.zip`,
    tmpDir: os.tmpdir(),
  });
  await fs.writeFile(target.path, bytes);
  return {
    archivePath: target.path,
    integrity: formatSha256Integrity(bytes),
    cleanup: target.cleanup,
  };
}

export function resolveLatestVersionFromPackage(detail: JunoHubPackageDetail): string | null {
  return detail.package?.latestVersion ?? detail.package?.tags?.latest ?? null;
}

export function isJunoHubFamilySkill(detail: JunoHubPackageDetail | JunoHubSkillDetail): boolean {
  if ("package" in detail) {
    return detail.package?.family === "skill";
  }
  return Boolean(detail.skill);
}

export function satisfiesPluginApiRange(
  pluginApiVersion: string,
  pluginApiRange?: string | null,
): boolean {
  if (!pluginApiRange) {
    return true;
  }
  return satisfiesSemverRange(pluginApiVersion, pluginApiRange);
}

export function satisfiesGatewayMinimum(
  currentVersion: string,
  minGatewayVersion?: string | null,
): boolean {
  if (!minGatewayVersion) {
    return true;
  }
  const current = parseSemver(currentVersion);
  const minimum = parseSemver(minGatewayVersion);
  if (!current || !minimum) {
    return false;
  }
  return isAtLeast(current, minimum);
}
