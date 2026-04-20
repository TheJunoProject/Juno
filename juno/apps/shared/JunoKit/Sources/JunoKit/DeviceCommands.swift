import Foundation

public enum JunoDeviceCommand: String, Codable, Sendable {
    case status = "device.status"
    case info = "device.info"
}

public enum JunoBatteryState: String, Codable, Sendable {
    case unknown
    case unplugged
    case charging
    case full
}

public enum JunoThermalState: String, Codable, Sendable {
    case nominal
    case fair
    case serious
    case critical
}

public enum JunoNetworkPathStatus: String, Codable, Sendable {
    case satisfied
    case unsatisfied
    case requiresConnection
}

public enum JunoNetworkInterfaceType: String, Codable, Sendable {
    case wifi
    case cellular
    case wired
    case other
}

public struct JunoBatteryStatusPayload: Codable, Sendable, Equatable {
    public var level: Double?
    public var state: JunoBatteryState
    public var lowPowerModeEnabled: Bool

    public init(level: Double?, state: JunoBatteryState, lowPowerModeEnabled: Bool) {
        self.level = level
        self.state = state
        self.lowPowerModeEnabled = lowPowerModeEnabled
    }
}

public struct JunoThermalStatusPayload: Codable, Sendable, Equatable {
    public var state: JunoThermalState

    public init(state: JunoThermalState) {
        self.state = state
    }
}

public struct JunoStorageStatusPayload: Codable, Sendable, Equatable {
    public var totalBytes: Int64
    public var freeBytes: Int64
    public var usedBytes: Int64

    public init(totalBytes: Int64, freeBytes: Int64, usedBytes: Int64) {
        self.totalBytes = totalBytes
        self.freeBytes = freeBytes
        self.usedBytes = usedBytes
    }
}

public struct JunoNetworkStatusPayload: Codable, Sendable, Equatable {
    public var status: JunoNetworkPathStatus
    public var isExpensive: Bool
    public var isConstrained: Bool
    public var interfaces: [JunoNetworkInterfaceType]

    public init(
        status: JunoNetworkPathStatus,
        isExpensive: Bool,
        isConstrained: Bool,
        interfaces: [JunoNetworkInterfaceType])
    {
        self.status = status
        self.isExpensive = isExpensive
        self.isConstrained = isConstrained
        self.interfaces = interfaces
    }
}

public struct JunoDeviceStatusPayload: Codable, Sendable, Equatable {
    public var battery: JunoBatteryStatusPayload
    public var thermal: JunoThermalStatusPayload
    public var storage: JunoStorageStatusPayload
    public var network: JunoNetworkStatusPayload
    public var uptimeSeconds: Double

    public init(
        battery: JunoBatteryStatusPayload,
        thermal: JunoThermalStatusPayload,
        storage: JunoStorageStatusPayload,
        network: JunoNetworkStatusPayload,
        uptimeSeconds: Double)
    {
        self.battery = battery
        self.thermal = thermal
        self.storage = storage
        self.network = network
        self.uptimeSeconds = uptimeSeconds
    }
}

public struct JunoDeviceInfoPayload: Codable, Sendable, Equatable {
    public var deviceName: String
    public var modelIdentifier: String
    public var systemName: String
    public var systemVersion: String
    public var appVersion: String
    public var appBuild: String
    public var locale: String

    public init(
        deviceName: String,
        modelIdentifier: String,
        systemName: String,
        systemVersion: String,
        appVersion: String,
        appBuild: String,
        locale: String)
    {
        self.deviceName = deviceName
        self.modelIdentifier = modelIdentifier
        self.systemName = systemName
        self.systemVersion = systemVersion
        self.appVersion = appVersion
        self.appBuild = appBuild
        self.locale = locale
    }
}
