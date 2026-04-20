package ai.juno.app.protocol

import org.junit.Assert.assertEquals
import org.junit.Test

class JunoProtocolConstantsTest {
  @Test
  fun canvasCommandsUseStableStrings() {
    assertEquals("canvas.present", JunoCanvasCommand.Present.rawValue)
    assertEquals("canvas.hide", JunoCanvasCommand.Hide.rawValue)
    assertEquals("canvas.navigate", JunoCanvasCommand.Navigate.rawValue)
    assertEquals("canvas.eval", JunoCanvasCommand.Eval.rawValue)
    assertEquals("canvas.snapshot", JunoCanvasCommand.Snapshot.rawValue)
  }

  @Test
  fun a2uiCommandsUseStableStrings() {
    assertEquals("canvas.a2ui.push", JunoCanvasA2UICommand.Push.rawValue)
    assertEquals("canvas.a2ui.pushJSONL", JunoCanvasA2UICommand.PushJSONL.rawValue)
    assertEquals("canvas.a2ui.reset", JunoCanvasA2UICommand.Reset.rawValue)
  }

  @Test
  fun capabilitiesUseStableStrings() {
    assertEquals("canvas", JunoCapability.Canvas.rawValue)
    assertEquals("camera", JunoCapability.Camera.rawValue)
    assertEquals("voiceWake", JunoCapability.VoiceWake.rawValue)
    assertEquals("location", JunoCapability.Location.rawValue)
    assertEquals("sms", JunoCapability.Sms.rawValue)
    assertEquals("device", JunoCapability.Device.rawValue)
    assertEquals("notifications", JunoCapability.Notifications.rawValue)
    assertEquals("system", JunoCapability.System.rawValue)
    assertEquals("photos", JunoCapability.Photos.rawValue)
    assertEquals("contacts", JunoCapability.Contacts.rawValue)
    assertEquals("calendar", JunoCapability.Calendar.rawValue)
    assertEquals("motion", JunoCapability.Motion.rawValue)
    assertEquals("callLog", JunoCapability.CallLog.rawValue)
  }

  @Test
  fun cameraCommandsUseStableStrings() {
    assertEquals("camera.list", JunoCameraCommand.List.rawValue)
    assertEquals("camera.snap", JunoCameraCommand.Snap.rawValue)
    assertEquals("camera.clip", JunoCameraCommand.Clip.rawValue)
  }

  @Test
  fun notificationsCommandsUseStableStrings() {
    assertEquals("notifications.list", JunoNotificationsCommand.List.rawValue)
    assertEquals("notifications.actions", JunoNotificationsCommand.Actions.rawValue)
  }

  @Test
  fun deviceCommandsUseStableStrings() {
    assertEquals("device.status", JunoDeviceCommand.Status.rawValue)
    assertEquals("device.info", JunoDeviceCommand.Info.rawValue)
    assertEquals("device.permissions", JunoDeviceCommand.Permissions.rawValue)
    assertEquals("device.health", JunoDeviceCommand.Health.rawValue)
  }

  @Test
  fun systemCommandsUseStableStrings() {
    assertEquals("system.notify", JunoSystemCommand.Notify.rawValue)
  }

  @Test
  fun photosCommandsUseStableStrings() {
    assertEquals("photos.latest", JunoPhotosCommand.Latest.rawValue)
  }

  @Test
  fun contactsCommandsUseStableStrings() {
    assertEquals("contacts.search", JunoContactsCommand.Search.rawValue)
    assertEquals("contacts.add", JunoContactsCommand.Add.rawValue)
  }

  @Test
  fun calendarCommandsUseStableStrings() {
    assertEquals("calendar.events", JunoCalendarCommand.Events.rawValue)
    assertEquals("calendar.add", JunoCalendarCommand.Add.rawValue)
  }

  @Test
  fun motionCommandsUseStableStrings() {
    assertEquals("motion.activity", JunoMotionCommand.Activity.rawValue)
    assertEquals("motion.pedometer", JunoMotionCommand.Pedometer.rawValue)
  }

  @Test
  fun smsCommandsUseStableStrings() {
    assertEquals("sms.send", JunoSmsCommand.Send.rawValue)
    assertEquals("sms.search", JunoSmsCommand.Search.rawValue)
  }

  @Test
  fun callLogCommandsUseStableStrings() {
    assertEquals("callLog.search", JunoCallLogCommand.Search.rawValue)
  }

}
