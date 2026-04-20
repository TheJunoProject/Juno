export type InstallRecordBase = {
  source: "npm" | "archive" | "path" | "junohub";
  spec?: string;
  sourcePath?: string;
  installPath?: string;
  version?: string;
  resolvedName?: string;
  resolvedVersion?: string;
  resolvedSpec?: string;
  integrity?: string;
  shasum?: string;
  resolvedAt?: string;
  installedAt?: string;
  junohubUrl?: string;
  junohubPackage?: string;
  junohubFamily?: "code-plugin" | "bundle-plugin";
  junohubChannel?: "official" | "community" | "private";
};
