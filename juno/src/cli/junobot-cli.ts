import type { Command } from "commander";
import { formatDocsLink } from "../terminal/links.js";
import { theme } from "../terminal/theme.js";
import { registerQrCli } from "./qr-cli.js";

export function registerJunobotCli(program: Command) {
  const junobot = program
    .command("junobot")
    .description("Legacy junobot command aliases")
    .addHelpText(
      "after",
      () =>
        `\n${theme.muted("Docs:")} ${formatDocsLink("/cli/junobot", "docs.juno.ai/cli/junobot")}\n`,
    );
  registerQrCli(junobot);
}
