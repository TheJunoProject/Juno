export type JunoPiCodingAgentSkillSourceAugmentation = never;

declare module "@mariozechner/pi-coding-agent" {
  interface Skill {
    // Juno relies on the source identifier returned by pi skill loaders.
    source: string;
  }
}
