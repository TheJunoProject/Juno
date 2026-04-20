import type { JunoConfig } from "../config/types.juno.js";
import type { PluginRuntime } from "./runtime/types.js";
import type { JunoPluginApi, PluginLogger } from "./types.js";

export type BuildPluginApiParams = {
  id: string;
  name: string;
  version?: string;
  description?: string;
  source: string;
  rootDir?: string;
  registrationMode: JunoPluginApi["registrationMode"];
  config: JunoConfig;
  pluginConfig?: Record<string, unknown>;
  runtime: PluginRuntime;
  logger: PluginLogger;
  resolvePath: (input: string) => string;
  handlers?: Partial<
    Pick<
      JunoPluginApi,
      | "registerTool"
      | "registerHook"
      | "registerHttpRoute"
      | "registerChannel"
      | "registerGatewayMethod"
      | "registerCli"
      | "registerReload"
      | "registerNodeHostCommand"
      | "registerSecurityAuditCollector"
      | "registerService"
      | "registerCliBackend"
      | "registerTextTransforms"
      | "registerConfigMigration"
      | "registerAutoEnableProbe"
      | "registerProvider"
      | "registerSpeechProvider"
      | "registerRealtimeTranscriptionProvider"
      | "registerRealtimeVoiceProvider"
      | "registerMediaUnderstandingProvider"
      | "registerImageGenerationProvider"
      | "registerVideoGenerationProvider"
      | "registerMusicGenerationProvider"
      | "registerWebFetchProvider"
      | "registerWebSearchProvider"
      | "registerInteractiveHandler"
      | "onConversationBindingResolved"
      | "registerCommand"
      | "registerContextEngine"
      | "registerCompactionProvider"
      | "registerAgentHarness"
      | "registerDetachedTaskRuntime"
      | "registerMemoryCapability"
      | "registerMemoryPromptSection"
      | "registerMemoryPromptSupplement"
      | "registerMemoryCorpusSupplement"
      | "registerMemoryFlushPlan"
      | "registerMemoryRuntime"
      | "registerMemoryEmbeddingProvider"
      | "on"
    >
  >;
};

const noopRegisterTool: JunoPluginApi["registerTool"] = () => {};
const noopRegisterHook: JunoPluginApi["registerHook"] = () => {};
const noopRegisterHttpRoute: JunoPluginApi["registerHttpRoute"] = () => {};
const noopRegisterChannel: JunoPluginApi["registerChannel"] = () => {};
const noopRegisterGatewayMethod: JunoPluginApi["registerGatewayMethod"] = () => {};
const noopRegisterCli: JunoPluginApi["registerCli"] = () => {};
const noopRegisterReload: JunoPluginApi["registerReload"] = () => {};
const noopRegisterNodeHostCommand: JunoPluginApi["registerNodeHostCommand"] = () => {};
const noopRegisterSecurityAuditCollector: JunoPluginApi["registerSecurityAuditCollector"] =
  () => {};
const noopRegisterService: JunoPluginApi["registerService"] = () => {};
const noopRegisterCliBackend: JunoPluginApi["registerCliBackend"] = () => {};
const noopRegisterTextTransforms: JunoPluginApi["registerTextTransforms"] = () => {};
const noopRegisterConfigMigration: JunoPluginApi["registerConfigMigration"] = () => {};
const noopRegisterAutoEnableProbe: JunoPluginApi["registerAutoEnableProbe"] = () => {};
const noopRegisterProvider: JunoPluginApi["registerProvider"] = () => {};
const noopRegisterSpeechProvider: JunoPluginApi["registerSpeechProvider"] = () => {};
const noopRegisterRealtimeTranscriptionProvider: JunoPluginApi["registerRealtimeTranscriptionProvider"] =
  () => {};
const noopRegisterRealtimeVoiceProvider: JunoPluginApi["registerRealtimeVoiceProvider"] =
  () => {};
const noopRegisterMediaUnderstandingProvider: JunoPluginApi["registerMediaUnderstandingProvider"] =
  () => {};
const noopRegisterImageGenerationProvider: JunoPluginApi["registerImageGenerationProvider"] =
  () => {};
const noopRegisterVideoGenerationProvider: JunoPluginApi["registerVideoGenerationProvider"] =
  () => {};
const noopRegisterMusicGenerationProvider: JunoPluginApi["registerMusicGenerationProvider"] =
  () => {};
const noopRegisterWebFetchProvider: JunoPluginApi["registerWebFetchProvider"] = () => {};
const noopRegisterWebSearchProvider: JunoPluginApi["registerWebSearchProvider"] = () => {};
const noopRegisterInteractiveHandler: JunoPluginApi["registerInteractiveHandler"] = () => {};
const noopOnConversationBindingResolved: JunoPluginApi["onConversationBindingResolved"] =
  () => {};
const noopRegisterCommand: JunoPluginApi["registerCommand"] = () => {};
const noopRegisterContextEngine: JunoPluginApi["registerContextEngine"] = () => {};
const noopRegisterCompactionProvider: JunoPluginApi["registerCompactionProvider"] = () => {};
const noopRegisterAgentHarness: JunoPluginApi["registerAgentHarness"] = () => {};
const noopRegisterDetachedTaskRuntime: JunoPluginApi["registerDetachedTaskRuntime"] = () => {};
const noopRegisterMemoryCapability: JunoPluginApi["registerMemoryCapability"] = () => {};
const noopRegisterMemoryPromptSection: JunoPluginApi["registerMemoryPromptSection"] = () => {};
const noopRegisterMemoryPromptSupplement: JunoPluginApi["registerMemoryPromptSupplement"] =
  () => {};
const noopRegisterMemoryCorpusSupplement: JunoPluginApi["registerMemoryCorpusSupplement"] =
  () => {};
const noopRegisterMemoryFlushPlan: JunoPluginApi["registerMemoryFlushPlan"] = () => {};
const noopRegisterMemoryRuntime: JunoPluginApi["registerMemoryRuntime"] = () => {};
const noopRegisterMemoryEmbeddingProvider: JunoPluginApi["registerMemoryEmbeddingProvider"] =
  () => {};
const noopOn: JunoPluginApi["on"] = () => {};

export function buildPluginApi(params: BuildPluginApiParams): JunoPluginApi {
  const handlers = params.handlers ?? {};
  return {
    id: params.id,
    name: params.name,
    version: params.version,
    description: params.description,
    source: params.source,
    rootDir: params.rootDir,
    registrationMode: params.registrationMode,
    config: params.config,
    pluginConfig: params.pluginConfig,
    runtime: params.runtime,
    logger: params.logger,
    registerTool: handlers.registerTool ?? noopRegisterTool,
    registerHook: handlers.registerHook ?? noopRegisterHook,
    registerHttpRoute: handlers.registerHttpRoute ?? noopRegisterHttpRoute,
    registerChannel: handlers.registerChannel ?? noopRegisterChannel,
    registerGatewayMethod: handlers.registerGatewayMethod ?? noopRegisterGatewayMethod,
    registerCli: handlers.registerCli ?? noopRegisterCli,
    registerReload: handlers.registerReload ?? noopRegisterReload,
    registerNodeHostCommand: handlers.registerNodeHostCommand ?? noopRegisterNodeHostCommand,
    registerSecurityAuditCollector:
      handlers.registerSecurityAuditCollector ?? noopRegisterSecurityAuditCollector,
    registerService: handlers.registerService ?? noopRegisterService,
    registerCliBackend: handlers.registerCliBackend ?? noopRegisterCliBackend,
    registerTextTransforms: handlers.registerTextTransforms ?? noopRegisterTextTransforms,
    registerConfigMigration: handlers.registerConfigMigration ?? noopRegisterConfigMigration,
    registerAutoEnableProbe: handlers.registerAutoEnableProbe ?? noopRegisterAutoEnableProbe,
    registerProvider: handlers.registerProvider ?? noopRegisterProvider,
    registerSpeechProvider: handlers.registerSpeechProvider ?? noopRegisterSpeechProvider,
    registerRealtimeTranscriptionProvider:
      handlers.registerRealtimeTranscriptionProvider ?? noopRegisterRealtimeTranscriptionProvider,
    registerRealtimeVoiceProvider:
      handlers.registerRealtimeVoiceProvider ?? noopRegisterRealtimeVoiceProvider,
    registerMediaUnderstandingProvider:
      handlers.registerMediaUnderstandingProvider ?? noopRegisterMediaUnderstandingProvider,
    registerImageGenerationProvider:
      handlers.registerImageGenerationProvider ?? noopRegisterImageGenerationProvider,
    registerVideoGenerationProvider:
      handlers.registerVideoGenerationProvider ?? noopRegisterVideoGenerationProvider,
    registerMusicGenerationProvider:
      handlers.registerMusicGenerationProvider ?? noopRegisterMusicGenerationProvider,
    registerWebFetchProvider: handlers.registerWebFetchProvider ?? noopRegisterWebFetchProvider,
    registerWebSearchProvider: handlers.registerWebSearchProvider ?? noopRegisterWebSearchProvider,
    registerInteractiveHandler:
      handlers.registerInteractiveHandler ?? noopRegisterInteractiveHandler,
    onConversationBindingResolved:
      handlers.onConversationBindingResolved ?? noopOnConversationBindingResolved,
    registerCommand: handlers.registerCommand ?? noopRegisterCommand,
    registerContextEngine: handlers.registerContextEngine ?? noopRegisterContextEngine,
    registerCompactionProvider:
      handlers.registerCompactionProvider ?? noopRegisterCompactionProvider,
    registerAgentHarness: handlers.registerAgentHarness ?? noopRegisterAgentHarness,
    registerDetachedTaskRuntime:
      handlers.registerDetachedTaskRuntime ?? noopRegisterDetachedTaskRuntime,
    registerMemoryCapability: handlers.registerMemoryCapability ?? noopRegisterMemoryCapability,
    registerMemoryPromptSection:
      handlers.registerMemoryPromptSection ?? noopRegisterMemoryPromptSection,
    registerMemoryPromptSupplement:
      handlers.registerMemoryPromptSupplement ?? noopRegisterMemoryPromptSupplement,
    registerMemoryCorpusSupplement:
      handlers.registerMemoryCorpusSupplement ?? noopRegisterMemoryCorpusSupplement,
    registerMemoryFlushPlan: handlers.registerMemoryFlushPlan ?? noopRegisterMemoryFlushPlan,
    registerMemoryRuntime: handlers.registerMemoryRuntime ?? noopRegisterMemoryRuntime,
    registerMemoryEmbeddingProvider:
      handlers.registerMemoryEmbeddingProvider ?? noopRegisterMemoryEmbeddingProvider,
    resolvePath: params.resolvePath,
    on: handlers.on ?? noopOn,
  };
}
