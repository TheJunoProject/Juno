import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import { validateExternalCodePluginPackageJson } from "../../packages/plugin-package-contract/src/index.ts";
import {
  collectExtensionPackageJsonCandidates,
  collectChangedPathsFromGitRange,
  collectChangedExtensionIdsFromPaths,
  collectPublishablePluginPackageErrors,
  parsePluginReleaseArgs,
  parsePluginReleaseSelection,
  parsePluginReleaseSelectionMode,
  resolvePublishablePluginVersion,
  resolveGitCommitSha,
  resolveChangedPublishablePluginPackages,
  resolveSelectedPublishablePluginPackages,
  type GitRangeSelection,
  type ParsedPluginReleaseArgs,
  type PluginReleaseSelectionMode,
} from "./plugin-npm-release.ts";

export {
  collectChangedExtensionIdsFromPaths,
  parsePluginReleaseArgs,
  parsePluginReleaseSelection,
  parsePluginReleaseSelectionMode,
  resolveChangedPublishablePluginPackages,
  resolveSelectedPublishablePluginPackages,
  type GitRangeSelection,
  type ParsedPluginReleaseArgs,
  type PluginReleaseSelectionMode,
};

export type PluginPackageJson = {
  name?: string;
  version?: string;
  private?: boolean;
  juno?: {
    extensions?: string[];
    install?: {
      npmSpec?: string;
    };
    compat?: {
      pluginApi?: string;
      minGatewayVersion?: string;
    };
    build?: {
      junoVersion?: string;
      pluginSdkVersion?: string;
    };
    release?: {
      publishToJunoHub?: boolean;
      publishToNpm?: boolean;
    };
  };
};

export type PublishablePluginPackage = {
  extensionId: string;
  packageDir: string;
  packageName: string;
  version: string;
  channel: "stable" | "beta";
  publishTag: "latest" | "beta";
};

export type PluginReleasePlanItem = PublishablePluginPackage & {
  alreadyPublished: boolean;
};

export type PluginReleasePlan = {
  all: PluginReleasePlanItem[];
  candidates: PluginReleasePlanItem[];
  skippedPublished: PluginReleasePlanItem[];
};

const JUNOHUB_DEFAULT_REGISTRY = "https://junohub.ai";
const SAFE_EXTENSION_ID_RE = /^[a-z0-9][a-z0-9._-]*$/;
const JUNOHUB_SHARED_RELEASE_INPUT_PATHS = [
  ".github/workflows/plugin-junohub-release.yml",
  ".github/actions/setup-node-env",
  "package.json",
  "pnpm-lock.yaml",
  "packages/plugin-package-contract/src/index.ts",
  "scripts/lib/npm-publish-plan.mjs",
  "scripts/lib/plugin-npm-release.ts",
  "scripts/lib/plugin-junohub-release.ts",
  "scripts/juno-npm-release-check.ts",
  "scripts/plugin-junohub-publish.sh",
  "scripts/plugin-junohub-release-check.ts",
  "scripts/plugin-junohub-release-plan.ts",
] as const;

function getRegistryBaseUrl(explicit?: string) {
  return (
    explicit?.trim() ||
    process.env.JUNOHUB_REGISTRY?.trim() ||
    process.env.JUNOHUB_SITE?.trim() ||
    JUNOHUB_DEFAULT_REGISTRY
  );
}

export function collectJunoHubPublishablePluginPackages(
  rootDir = resolve("."),
): PublishablePluginPackage[] {
  const publishable: PublishablePluginPackage[] = [];
  const validationErrors: string[] = [];

  for (const candidate of collectExtensionPackageJsonCandidates(rootDir)) {
    const { extensionId, packageDir, packageJson } = candidate;
    if (packageJson.juno?.release?.publishToJunoHub !== true) {
      continue;
    }
    if (!SAFE_EXTENSION_ID_RE.test(extensionId)) {
      validationErrors.push(
        `${extensionId}: extension directory name must match ^[a-z0-9][a-z0-9._-]*$ for JunoHub publish.`,
      );
      continue;
    }

    const errors = collectPublishablePluginPackageErrors({
      extensionId,
      packageDir,
      packageJson,
    });
    if (errors.length > 0) {
      validationErrors.push(...errors.map((error) => `${extensionId}: ${error}`));
      continue;
    }
    const contractValidation = validateExternalCodePluginPackageJson(packageJson);
    if (contractValidation.issues.length > 0) {
      validationErrors.push(
        ...contractValidation.issues.map((issue) => `${extensionId}: ${issue.message}`),
      );
      continue;
    }

    const resolvedVersion = resolvePublishablePluginVersion({
      extensionId,
      packageJson,
      validationErrors,
    });
    if (!resolvedVersion) {
      continue;
    }
    const { version, parsedVersion } = resolvedVersion;

    publishable.push({
      extensionId,
      packageDir,
      packageName: packageJson.name!.trim(),
      version,
      channel: parsedVersion.channel,
      publishTag: parsedVersion.channel === "beta" ? "beta" : "latest",
    });
  }

  if (validationErrors.length > 0) {
    throw new Error(
      `Publishable JunoHub plugin metadata validation failed:\n${validationErrors.map((error) => `- ${error}`).join("\n")}`,
    );
  }

  return publishable.toSorted((left, right) => left.packageName.localeCompare(right.packageName));
}

export function collectPluginJunoHubReleasePathsFromGitRange(params: {
  rootDir?: string;
  gitRange: GitRangeSelection;
}): string[] {
  return collectPluginJunoHubReleasePathsFromGitRangeForPathspecs(params, ["extensions"]);
}

function collectPluginJunoHubRelevantPathsFromGitRange(params: {
  rootDir?: string;
  gitRange: GitRangeSelection;
}): string[] {
  return collectPluginJunoHubReleasePathsFromGitRangeForPathspecs(params, [
    "extensions",
    ...JUNOHUB_SHARED_RELEASE_INPUT_PATHS,
  ]);
}

function collectPluginJunoHubReleasePathsFromGitRangeForPathspecs(
  params: {
    rootDir?: string;
    gitRange: GitRangeSelection;
  },
  pathspecs: readonly string[],
): string[] {
  return collectChangedPathsFromGitRange({
    rootDir: params.rootDir,
    gitRange: params.gitRange,
    pathspecs,
  });
}

function hasSharedJunoHubReleaseInputChanges(changedPaths: readonly string[]) {
  return changedPaths.some((path) =>
    JUNOHUB_SHARED_RELEASE_INPUT_PATHS.some(
      (sharedPath) => path === sharedPath || path.startsWith(`${sharedPath}/`),
    ),
  );
}

export function resolveChangedJunoHubPublishablePluginPackages(params: {
  plugins: PublishablePluginPackage[];
  changedPaths: readonly string[];
}): PublishablePluginPackage[] {
  return resolveChangedPublishablePluginPackages({
    plugins: params.plugins,
    changedExtensionIds: collectChangedExtensionIdsFromPaths(params.changedPaths),
  });
}

export function resolveSelectedJunoHubPublishablePluginPackages(params: {
  plugins: PublishablePluginPackage[];
  selection?: string[];
  selectionMode?: PluginReleaseSelectionMode;
  gitRange?: GitRangeSelection;
  rootDir?: string;
}): PublishablePluginPackage[] {
  if (params.selectionMode === "all-publishable") {
    return params.plugins;
  }
  if (params.selection && params.selection.length > 0) {
    return resolveSelectedPublishablePluginPackages({
      plugins: params.plugins,
      selection: params.selection,
    });
  }
  if (params.gitRange) {
    const changedPaths = collectPluginJunoHubRelevantPathsFromGitRange({
      rootDir: params.rootDir,
      gitRange: params.gitRange,
    });
    if (hasSharedJunoHubReleaseInputChanges(changedPaths)) {
      return params.plugins;
    }
    return resolveChangedJunoHubPublishablePluginPackages({
      plugins: params.plugins,
      changedPaths,
    });
  }
  return params.plugins;
}

function readPackageManifestAtGitRef(params: {
  rootDir?: string;
  ref: string;
  packageDir: string;
}): PluginPackageJson | null {
  const rootDir = params.rootDir ?? resolve(".");
  const commitSha = resolveGitCommitSha(rootDir, params.ref, "ref");
  try {
    const raw = execFileSync("git", ["show", `${commitSha}:${params.packageDir}/package.json`], {
      cwd: rootDir,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
    return JSON.parse(raw) as PluginPackageJson;
  } catch {
    return null;
  }
}

export function collectJunoHubVersionGateErrors(params: {
  plugins: PublishablePluginPackage[];
  gitRange: GitRangeSelection;
  rootDir?: string;
}): string[] {
  const changedPaths = collectPluginJunoHubReleasePathsFromGitRange({
    rootDir: params.rootDir,
    gitRange: params.gitRange,
  });
  const changedPlugins = resolveChangedJunoHubPublishablePluginPackages({
    plugins: params.plugins,
    changedPaths,
  });

  const errors: string[] = [];
  for (const plugin of changedPlugins) {
    const baseManifest = readPackageManifestAtGitRef({
      rootDir: params.rootDir,
      ref: params.gitRange.baseRef,
      packageDir: plugin.packageDir,
    });
    if (baseManifest?.juno?.release?.publishToJunoHub !== true) {
      continue;
    }
    const baseVersion =
      typeof baseManifest.version === "string" && baseManifest.version.trim()
        ? baseManifest.version.trim()
        : null;
    if (baseVersion === null || baseVersion !== plugin.version) {
      continue;
    }
    errors.push(
      `${plugin.packageName}@${plugin.version}: changed publishable plugin still has the same version in package.json.`,
    );
  }

  return errors;
}

export async function isPluginVersionPublishedOnJunoHub(
  packageName: string,
  version: string,
  options: {
    fetchImpl?: typeof fetch;
    registryBaseUrl?: string;
  } = {},
): Promise<boolean> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const url = new URL(
    `/api/v1/packages/${encodeURIComponent(packageName)}/versions/${encodeURIComponent(version)}`,
    getRegistryBaseUrl(options.registryBaseUrl),
  );
  const response = await fetchImpl(url, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
  });

  if (response.status === 404) {
    return false;
  }
  if (response.ok) {
    return true;
  }

  throw new Error(
    `Failed to query JunoHub for ${packageName}@${version}: ${response.status} ${response.statusText}`,
  );
}

export async function collectPluginJunoHubReleasePlan(params?: {
  rootDir?: string;
  selection?: string[];
  selectionMode?: PluginReleaseSelectionMode;
  gitRange?: GitRangeSelection;
  registryBaseUrl?: string;
  fetchImpl?: typeof fetch;
}): Promise<PluginReleasePlan> {
  const allPublishable = collectJunoHubPublishablePluginPackages(params?.rootDir);
  const selectedPublishable = resolveSelectedJunoHubPublishablePluginPackages({
    plugins: allPublishable,
    selection: params?.selection,
    selectionMode: params?.selectionMode,
    gitRange: params?.gitRange,
    rootDir: params?.rootDir,
  });

  const all = await Promise.all(
    selectedPublishable.map(async (plugin) =>
      Object.assign({}, plugin, {
        alreadyPublished: await isPluginVersionPublishedOnJunoHub(
          plugin.packageName,
          plugin.version,
          { registryBaseUrl: params?.registryBaseUrl, fetchImpl: params?.fetchImpl },
        ),
      }),
    ),
  );

  return {
    all,
    candidates: all.filter((plugin) => !plugin.alreadyPublished),
    skippedPublished: all.filter((plugin) => plugin.alreadyPublished),
  };
}
