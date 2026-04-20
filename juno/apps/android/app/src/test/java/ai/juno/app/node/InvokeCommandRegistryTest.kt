package ai.juno.app.node

import ai.juno.app.protocol.JunoCalendarCommand
import ai.juno.app.protocol.JunoCameraCommand
import ai.juno.app.protocol.JunoCallLogCommand
import ai.juno.app.protocol.JunoCapability
import ai.juno.app.protocol.JunoContactsCommand
import ai.juno.app.protocol.JunoDeviceCommand
import ai.juno.app.protocol.JunoLocationCommand
import ai.juno.app.protocol.JunoMotionCommand
import ai.juno.app.protocol.JunoNotificationsCommand
import ai.juno.app.protocol.JunoPhotosCommand
import ai.juno.app.protocol.JunoSmsCommand
import ai.juno.app.protocol.JunoSystemCommand
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class InvokeCommandRegistryTest {
  private val coreCapabilities =
    setOf(
      JunoCapability.Canvas.rawValue,
      JunoCapability.Device.rawValue,
      JunoCapability.Notifications.rawValue,
      JunoCapability.System.rawValue,
      JunoCapability.Photos.rawValue,
      JunoCapability.Contacts.rawValue,
      JunoCapability.Calendar.rawValue,
    )

  private val optionalCapabilities =
    setOf(
      JunoCapability.Camera.rawValue,
      JunoCapability.Location.rawValue,
      JunoCapability.Sms.rawValue,
      JunoCapability.CallLog.rawValue,
      JunoCapability.VoiceWake.rawValue,
      JunoCapability.Motion.rawValue,
    )

  private val coreCommands =
    setOf(
      JunoDeviceCommand.Status.rawValue,
      JunoDeviceCommand.Info.rawValue,
      JunoDeviceCommand.Permissions.rawValue,
      JunoDeviceCommand.Health.rawValue,
      JunoNotificationsCommand.List.rawValue,
      JunoNotificationsCommand.Actions.rawValue,
      JunoSystemCommand.Notify.rawValue,
      JunoPhotosCommand.Latest.rawValue,
      JunoContactsCommand.Search.rawValue,
      JunoContactsCommand.Add.rawValue,
      JunoCalendarCommand.Events.rawValue,
      JunoCalendarCommand.Add.rawValue,
    )

  private val optionalCommands =
    setOf(
      JunoCameraCommand.Snap.rawValue,
      JunoCameraCommand.Clip.rawValue,
      JunoCameraCommand.List.rawValue,
      JunoLocationCommand.Get.rawValue,
      JunoMotionCommand.Activity.rawValue,
      JunoMotionCommand.Pedometer.rawValue,
      JunoSmsCommand.Send.rawValue,
      JunoSmsCommand.Search.rawValue,
      JunoCallLogCommand.Search.rawValue,
    )

  private val debugCommands = setOf("debug.logs", "debug.ed25519")

  @Test
  fun advertisedCapabilities_respectsFeatureAvailability() {
    val capabilities = InvokeCommandRegistry.advertisedCapabilities(defaultFlags())

    assertContainsAll(capabilities, coreCapabilities)
    assertMissingAll(capabilities, optionalCapabilities)
  }

  @Test
  fun advertisedCapabilities_includesFeatureCapabilitiesWhenEnabled() {
    val capabilities =
      InvokeCommandRegistry.advertisedCapabilities(
        defaultFlags(
          cameraEnabled = true,
          locationEnabled = true,
          sendSmsAvailable = true,
          readSmsAvailable = true,
          smsSearchPossible = true,
          callLogAvailable = true,
          voiceWakeEnabled = true,
          motionActivityAvailable = true,
          motionPedometerAvailable = true,
        ),
      )

    assertContainsAll(capabilities, coreCapabilities + optionalCapabilities)
  }

  @Test
  fun advertisedCommands_respectsFeatureAvailability() {
    val commands = InvokeCommandRegistry.advertisedCommands(defaultFlags())

    assertContainsAll(commands, coreCommands)
    assertMissingAll(commands, optionalCommands + debugCommands)
  }

  @Test
  fun advertisedCommands_includesFeatureCommandsWhenEnabled() {
    val commands =
      InvokeCommandRegistry.advertisedCommands(
        defaultFlags(
          cameraEnabled = true,
          locationEnabled = true,
          sendSmsAvailable = true,
          readSmsAvailable = true,
          smsSearchPossible = true,
          callLogAvailable = true,
          motionActivityAvailable = true,
          motionPedometerAvailable = true,
          debugBuild = true,
        ),
      )

    assertContainsAll(commands, coreCommands + optionalCommands + debugCommands)
  }

  @Test
  fun advertisedCommands_onlyIncludesSupportedMotionCommands() {
    val commands =
      InvokeCommandRegistry.advertisedCommands(
        NodeRuntimeFlags(
          cameraEnabled = false,
          locationEnabled = false,
          sendSmsAvailable = false,
          readSmsAvailable = false,
          smsSearchPossible = false,
          callLogAvailable = false,
          voiceWakeEnabled = false,
          motionActivityAvailable = true,
          motionPedometerAvailable = false,
          debugBuild = false,
        ),
      )

    assertTrue(commands.contains(JunoMotionCommand.Activity.rawValue))
    assertFalse(commands.contains(JunoMotionCommand.Pedometer.rawValue))
  }

  @Test
  fun advertisedCommands_splitsSmsSendAndSearchAvailability() {
    val readOnlyCommands =
      InvokeCommandRegistry.advertisedCommands(
        defaultFlags(readSmsAvailable = true, smsSearchPossible = true),
      )
    val sendOnlyCommands =
      InvokeCommandRegistry.advertisedCommands(
        defaultFlags(sendSmsAvailable = true),
      )
    val requestableSearchCommands =
      InvokeCommandRegistry.advertisedCommands(
        defaultFlags(smsSearchPossible = true),
      )

    assertTrue(readOnlyCommands.contains(JunoSmsCommand.Search.rawValue))
    assertFalse(readOnlyCommands.contains(JunoSmsCommand.Send.rawValue))
    assertTrue(sendOnlyCommands.contains(JunoSmsCommand.Send.rawValue))
    assertFalse(sendOnlyCommands.contains(JunoSmsCommand.Search.rawValue))
    assertTrue(requestableSearchCommands.contains(JunoSmsCommand.Search.rawValue))
  }

  @Test
  fun advertisedCapabilities_includeSmsWhenEitherSmsPathIsAvailable() {
    val readOnlyCapabilities =
      InvokeCommandRegistry.advertisedCapabilities(
        defaultFlags(readSmsAvailable = true),
      )
    val sendOnlyCapabilities =
      InvokeCommandRegistry.advertisedCapabilities(
        defaultFlags(sendSmsAvailable = true),
      )
    val requestableSearchCapabilities =
      InvokeCommandRegistry.advertisedCapabilities(
        defaultFlags(smsSearchPossible = true),
      )

    assertTrue(readOnlyCapabilities.contains(JunoCapability.Sms.rawValue))
    assertTrue(sendOnlyCapabilities.contains(JunoCapability.Sms.rawValue))
    assertFalse(requestableSearchCapabilities.contains(JunoCapability.Sms.rawValue))
  }

  @Test
  fun advertisedCommands_excludesCallLogWhenUnavailable() {
    val commands = InvokeCommandRegistry.advertisedCommands(defaultFlags(callLogAvailable = false))

    assertFalse(commands.contains(JunoCallLogCommand.Search.rawValue))
  }

  @Test
  fun advertisedCapabilities_excludesCallLogWhenUnavailable() {
    val capabilities = InvokeCommandRegistry.advertisedCapabilities(defaultFlags(callLogAvailable = false))

    assertFalse(capabilities.contains(JunoCapability.CallLog.rawValue))
  }

  @Test
  fun advertisedCapabilities_includesVoiceWakeWithoutAdvertisingCommands() {
    val capabilities = InvokeCommandRegistry.advertisedCapabilities(defaultFlags(voiceWakeEnabled = true))
    val commands = InvokeCommandRegistry.advertisedCommands(defaultFlags(voiceWakeEnabled = true))

    assertTrue(capabilities.contains(JunoCapability.VoiceWake.rawValue))
    assertFalse(commands.any { it.contains("voice", ignoreCase = true) })
  }

  @Test
  fun find_returnsForegroundMetadataForCameraCommands() {
    val list = InvokeCommandRegistry.find(JunoCameraCommand.List.rawValue)
    val location = InvokeCommandRegistry.find(JunoLocationCommand.Get.rawValue)

    assertNotNull(list)
    assertEquals(true, list?.requiresForeground)
    assertNotNull(location)
    assertEquals(false, location?.requiresForeground)
  }

  @Test
  fun find_returnsNullForUnknownCommand() {
    assertNull(InvokeCommandRegistry.find("not.real"))
  }

  private fun defaultFlags(
    cameraEnabled: Boolean = false,
    locationEnabled: Boolean = false,
    sendSmsAvailable: Boolean = false,
    readSmsAvailable: Boolean = false,
    smsSearchPossible: Boolean = false,
    callLogAvailable: Boolean = false,
    voiceWakeEnabled: Boolean = false,
    motionActivityAvailable: Boolean = false,
    motionPedometerAvailable: Boolean = false,
    debugBuild: Boolean = false,
  ): NodeRuntimeFlags =
    NodeRuntimeFlags(
      cameraEnabled = cameraEnabled,
      locationEnabled = locationEnabled,
      sendSmsAvailable = sendSmsAvailable,
      readSmsAvailable = readSmsAvailable,
      smsSearchPossible = smsSearchPossible,
      callLogAvailable = callLogAvailable,
      voiceWakeEnabled = voiceWakeEnabled,
      motionActivityAvailable = motionActivityAvailable,
      motionPedometerAvailable = motionPedometerAvailable,
      debugBuild = debugBuild,
    )

  private fun assertContainsAll(actual: List<String>, expected: Set<String>) {
    expected.forEach { value -> assertTrue(actual.contains(value)) }
  }

  private fun assertMissingAll(actual: List<String>, forbidden: Set<String>) {
    forbidden.forEach { value -> assertFalse(actual.contains(value)) }
  }
}
