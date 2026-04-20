import type { JunoConfig } from "../../config/types.juno.js";
import type { GetReplyOptions } from "../get-reply-options.types.js";
import type { FinalizedMsgContext } from "../templating.js";
import type { FormatAbortReplyText, TryFastAbortFromMessage } from "./abort.runtime-types.js";
import type { GetReplyFromConfig } from "./get-reply.types.js";
import type { ReplyDispatchKind, ReplyDispatcher } from "./reply-dispatcher.types.js";

export type DispatchFromConfigResult = {
  queuedFinal: boolean;
  counts: Record<ReplyDispatchKind, number>;
};

export type DispatchFromConfigParams = {
  ctx: FinalizedMsgContext;
  cfg: JunoConfig;
  dispatcher: ReplyDispatcher;
  replyOptions?: Omit<GetReplyOptions, "onToolResult" | "onBlockReply">;
  replyResolver?: GetReplyFromConfig;
  fastAbortResolver?: TryFastAbortFromMessage;
  formatAbortReplyTextResolver?: FormatAbortReplyText;
  /** Optional config override passed to getReplyFromConfig (e.g. per-sender timezone). */
  configOverride?: JunoConfig;
};

export type DispatchReplyFromConfig = (
  params: DispatchFromConfigParams,
) => Promise<DispatchFromConfigResult>;
