export const JUNO_CLI_ENV_VAR = "JUNO_CLI";
export const JUNO_CLI_ENV_VALUE = "1";

export function markJunoExecEnv<T extends Record<string, string | undefined>>(env: T): T {
  return {
    ...env,
    [JUNO_CLI_ENV_VAR]: JUNO_CLI_ENV_VALUE,
  };
}

export function ensureJunoExecMarkerOnProcess(
  env: NodeJS.ProcessEnv = process.env,
): NodeJS.ProcessEnv {
  env[JUNO_CLI_ENV_VAR] = JUNO_CLI_ENV_VALUE;
  return env;
}
