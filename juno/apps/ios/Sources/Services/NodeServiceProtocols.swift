import CoreLocation
import Foundation
import JunoKit
import UIKit

typealias JunoCameraSnapResult = (format: String, base64: String, width: Int, height: Int)
typealias JunoCameraClipResult = (format: String, base64: String, durationMs: Int, hasAudio: Bool)

protocol CameraServicing: Sendable {
    func listDevices() async -> [CameraController.CameraDeviceInfo]
    func snap(params: JunoCameraSnapParams) async throws -> JunoCameraSnapResult
    func clip(params: JunoCameraClipParams) async throws -> JunoCameraClipResult
}

protocol ScreenRecordingServicing: Sendable {
    func record(
        screenIndex: Int?,
        durationMs: Int?,
        fps: Double?,
        includeAudio: Bool?,
        outPath: String?) async throws -> String
}

@MainActor
protocol LocationServicing: Sendable {
    func authorizationStatus() -> CLAuthorizationStatus
    func accuracyAuthorization() -> CLAccuracyAuthorization
    func ensureAuthorization(mode: JunoLocationMode) async -> CLAuthorizationStatus
    func currentLocation(
        params: JunoLocationGetParams,
        desiredAccuracy: JunoLocationAccuracy,
        maxAgeMs: Int?,
        timeoutMs: Int?) async throws -> CLLocation
    func startLocationUpdates(
        desiredAccuracy: JunoLocationAccuracy,
        significantChangesOnly: Bool) -> AsyncStream<CLLocation>
    func stopLocationUpdates()
    func startMonitoringSignificantLocationChanges(onUpdate: @escaping @Sendable (CLLocation) -> Void)
    func stopMonitoringSignificantLocationChanges()
}

@MainActor
protocol DeviceStatusServicing: Sendable {
    func status() async throws -> JunoDeviceStatusPayload
    func info() -> JunoDeviceInfoPayload
}

protocol PhotosServicing: Sendable {
    func latest(params: JunoPhotosLatestParams) async throws -> JunoPhotosLatestPayload
}

protocol ContactsServicing: Sendable {
    func search(params: JunoContactsSearchParams) async throws -> JunoContactsSearchPayload
    func add(params: JunoContactsAddParams) async throws -> JunoContactsAddPayload
}

protocol CalendarServicing: Sendable {
    func events(params: JunoCalendarEventsParams) async throws -> JunoCalendarEventsPayload
    func add(params: JunoCalendarAddParams) async throws -> JunoCalendarAddPayload
}

protocol RemindersServicing: Sendable {
    func list(params: JunoRemindersListParams) async throws -> JunoRemindersListPayload
    func add(params: JunoRemindersAddParams) async throws -> JunoRemindersAddPayload
}

protocol MotionServicing: Sendable {
    func activities(params: JunoMotionActivityParams) async throws -> JunoMotionActivityPayload
    func pedometer(params: JunoPedometerParams) async throws -> JunoPedometerPayload
}

struct WatchMessagingStatus: Sendable, Equatable {
    var supported: Bool
    var paired: Bool
    var appInstalled: Bool
    var reachable: Bool
    var activationState: String
}

struct WatchQuickReplyEvent: Sendable, Equatable {
    var replyId: String
    var promptId: String
    var actionId: String
    var actionLabel: String?
    var sessionKey: String?
    var note: String?
    var sentAtMs: Int?
    var transport: String
}

struct WatchExecApprovalResolveEvent: Sendable, Equatable {
    var replyId: String
    var approvalId: String
    var decision: JunoWatchExecApprovalDecision
    var sentAtMs: Int?
    var transport: String
}

struct WatchExecApprovalSnapshotRequestEvent: Sendable, Equatable {
    var requestId: String
    var sentAtMs: Int?
    var transport: String
}

struct WatchNotificationSendResult: Sendable, Equatable {
    var deliveredImmediately: Bool
    var queuedForDelivery: Bool
    var transport: String
}

protocol WatchMessagingServicing: AnyObject, Sendable {
    func status() async -> WatchMessagingStatus
    func setStatusHandler(_ handler: (@Sendable (WatchMessagingStatus) -> Void)?)
    func setReplyHandler(_ handler: (@Sendable (WatchQuickReplyEvent) -> Void)?)
    func setExecApprovalResolveHandler(_ handler: (@Sendable (WatchExecApprovalResolveEvent) -> Void)?)
    func setExecApprovalSnapshotRequestHandler(
        _ handler: (@Sendable (WatchExecApprovalSnapshotRequestEvent) -> Void)?)
    func sendNotification(
        id: String,
        params: JunoWatchNotifyParams) async throws -> WatchNotificationSendResult
    func sendExecApprovalPrompt(
        _ message: JunoWatchExecApprovalPromptMessage) async throws -> WatchNotificationSendResult
    func sendExecApprovalResolved(
        _ message: JunoWatchExecApprovalResolvedMessage) async throws -> WatchNotificationSendResult
    func sendExecApprovalExpired(
        _ message: JunoWatchExecApprovalExpiredMessage) async throws -> WatchNotificationSendResult
    func syncExecApprovalSnapshot(
        _ message: JunoWatchExecApprovalSnapshotMessage) async throws -> WatchNotificationSendResult
}

extension CameraController: CameraServicing {}
extension ScreenRecordService: ScreenRecordingServicing {}
extension LocationService: LocationServicing {}
