import Foundation

public enum JunoLocationMode: String, Codable, Sendable, CaseIterable {
    case off
    case whileUsing
    case always
}
