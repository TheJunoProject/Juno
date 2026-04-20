import Foundation

// Stable identifier used for both the macOS LaunchAgent label and Nix-managed defaults suite.
// nix-juno writes app defaults into this suite to survive app bundle identifier churn.
let launchdLabel = "ai.juno.mac"
let gatewayLaunchdLabel = "ai.juno.gateway"
let onboardingVersionKey = "juno.onboardingVersion"
let onboardingSeenKey = "juno.onboardingSeen"
let currentOnboardingVersion = 7
let pauseDefaultsKey = "juno.pauseEnabled"
let iconAnimationsEnabledKey = "juno.iconAnimationsEnabled"
let swabbleEnabledKey = "juno.swabbleEnabled"
let swabbleTriggersKey = "juno.swabbleTriggers"
let voiceWakeTriggerChimeKey = "juno.voiceWakeTriggerChime"
let voiceWakeSendChimeKey = "juno.voiceWakeSendChime"
let showDockIconKey = "juno.showDockIcon"
let defaultVoiceWakeTriggers = ["juno"]
let voiceWakeMaxWords = 32
let voiceWakeMaxWordLength = 64
let voiceWakeMicKey = "juno.voiceWakeMicID"
let voiceWakeMicNameKey = "juno.voiceWakeMicName"
let voiceWakeLocaleKey = "juno.voiceWakeLocaleID"
let voiceWakeAdditionalLocalesKey = "juno.voiceWakeAdditionalLocaleIDs"
let voicePushToTalkEnabledKey = "juno.voicePushToTalkEnabled"
let voiceWakeTriggersTalkModeKey = "juno.voiceWakeTriggersTalkMode"
let talkEnabledKey = "juno.talkEnabled"
let iconOverrideKey = "juno.iconOverride"
let connectionModeKey = "juno.connectionMode"
let remoteTargetKey = "juno.remoteTarget"
let remoteIdentityKey = "juno.remoteIdentity"
let remoteProjectRootKey = "juno.remoteProjectRoot"
let remoteCliPathKey = "juno.remoteCliPath"
let canvasEnabledKey = "juno.canvasEnabled"
let cameraEnabledKey = "juno.cameraEnabled"
let systemRunPolicyKey = "juno.systemRunPolicy"
let systemRunAllowlistKey = "juno.systemRunAllowlist"
let systemRunEnabledKey = "juno.systemRunEnabled"
let locationModeKey = "juno.locationMode"
let locationPreciseKey = "juno.locationPreciseEnabled"
let peekabooBridgeEnabledKey = "juno.peekabooBridgeEnabled"
let deepLinkKeyKey = "juno.deepLinkKey"
let modelCatalogPathKey = "juno.modelCatalogPath"
let modelCatalogReloadKey = "juno.modelCatalogReload"
let cliInstallPromptedVersionKey = "juno.cliInstallPromptedVersion"
let heartbeatsEnabledKey = "juno.heartbeatsEnabled"
let debugPaneEnabledKey = "juno.debugPaneEnabled"
let debugFileLogEnabledKey = "juno.debug.fileLogEnabled"
let appLogLevelKey = "juno.debug.appLogLevel"
let voiceWakeSupported: Bool = ProcessInfo.processInfo.operatingSystemVersion.majorVersion >= 26
