#!/usr/bin/env -S node --import tsx

import { pathToFileURL } from "node:url";
import {
  collectPluginJunoHubReleasePlan,
  parsePluginReleaseArgs,
} from "./lib/plugin-junohub-release.ts";

export async function collectPluginReleasePlanForJunoHub(argv: string[]) {
  const { selection, selectionMode, baseRef, headRef } = parsePluginReleaseArgs(argv);
  return await collectPluginJunoHubReleasePlan({
    selection,
    selectionMode,
    gitRange: baseRef && headRef ? { baseRef, headRef } : undefined,
  });
}

if (import.meta.url === pathToFileURL(process.argv[1] ?? "").href) {
  const plan = await collectPluginReleasePlanForJunoHub(process.argv.slice(2));
  console.log(JSON.stringify(plan, null, 2));
}
