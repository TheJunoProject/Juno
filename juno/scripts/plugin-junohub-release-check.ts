#!/usr/bin/env -S node --import tsx

import { pathToFileURL } from "node:url";
import {
  collectJunoHubPublishablePluginPackages,
  collectJunoHubVersionGateErrors,
  parsePluginReleaseArgs,
  resolveSelectedJunoHubPublishablePluginPackages,
} from "./lib/plugin-junohub-release.ts";

export async function runPluginJunoHubReleaseCheck(argv: string[]) {
  const { selection, selectionMode, baseRef, headRef } = parsePluginReleaseArgs(argv);
  const publishable = collectJunoHubPublishablePluginPackages();
  const gitRange = baseRef && headRef ? { baseRef, headRef } : undefined;
  const selected = resolveSelectedJunoHubPublishablePluginPackages({
    plugins: publishable,
    selection,
    selectionMode,
    gitRange,
  });

  if (gitRange) {
    const errors = collectJunoHubVersionGateErrors({
      plugins: publishable,
      gitRange,
    });
    if (errors.length > 0) {
      throw new Error(
        `plugin-junohub-release-check: version bumps required before JunoHub publish:\n${errors
          .map((error) => `  - ${error}`)
          .join("\n")}`,
      );
    }
  }

  console.log("plugin-junohub-release-check: publishable plugin metadata looks OK.");
  if (gitRange && selected.length === 0) {
    console.log(
      `  - no publishable plugin package changes detected between ${gitRange.baseRef} and ${gitRange.headRef}`,
    );
  }
  for (const plugin of selected) {
    console.log(
      `  - ${plugin.packageName}@${plugin.version} (${plugin.channel}, ${plugin.extensionId})`,
    );
  }
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  await runPluginJunoHubReleaseCheck(process.argv.slice(2));
}
