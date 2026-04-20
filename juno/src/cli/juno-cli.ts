import type { Command } from "commander";
import { formatDocsLink } from "../terminal/links.js";
import { theme } from "../terminal/theme.js";
import { registerQrCli } from "./qr-cli.js";

export function registerJunobotCli(program: Command) {
  const juno = program
    .command("juno")
    .description("Legacy juno command aliases")
    .addHelpText(
      "after",
      () =>
        `\n${theme.muted("Docs:")} ${formatDocsLink("/cli/juno", "docs.juno.ai/cli/juno")}\n`,
    );
  registerQrCli(juno);
}
