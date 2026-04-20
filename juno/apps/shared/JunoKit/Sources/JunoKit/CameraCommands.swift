import Foundation

public enum JunoCameraCommand: String, Codable, Sendable {
    case list = "camera.list"
    case snap = "camera.snap"
    case clip = "camera.clip"
}

public enum JunoCameraFacing: String, Codable, Sendable {
    case back
    case front
}

public enum JunoCameraImageFormat: String, Codable, Sendable {
    case jpg
    case jpeg
}

public enum JunoCameraVideoFormat: String, Codable, Sendable {
    case mp4
}

public struct JunoCameraSnapParams: Codable, Sendable, Equatable {
    public var facing: JunoCameraFacing?
    public var maxWidth: Int?
    public var quality: Double?
    public var format: JunoCameraImageFormat?
    public var deviceId: String?
    public var delayMs: Int?

    public init(
        facing: JunoCameraFacing? = nil,
        maxWidth: Int? = nil,
        quality: Double? = nil,
        format: JunoCameraImageFormat? = nil,
        deviceId: String? = nil,
        delayMs: Int? = nil)
    {
        self.facing = facing
        self.maxWidth = maxWidth
        self.quality = quality
        self.format = format
        self.deviceId = deviceId
        self.delayMs = delayMs
    }
}

public struct JunoCameraClipParams: Codable, Sendable, Equatable {
    public var facing: JunoCameraFacing?
    public var durationMs: Int?
    public var includeAudio: Bool?
    public var format: JunoCameraVideoFormat?
    public var deviceId: String?

    public init(
        facing: JunoCameraFacing? = nil,
        durationMs: Int? = nil,
        includeAudio: Bool? = nil,
        format: JunoCameraVideoFormat? = nil,
        deviceId: String? = nil)
    {
        self.facing = facing
        self.durationMs = durationMs
        self.includeAudio = includeAudio
        self.format = format
        self.deviceId = deviceId
    }
}
