import Foundation

public enum JunoRemindersCommand: String, Codable, Sendable {
    case list = "reminders.list"
    case add = "reminders.add"
}

public enum JunoReminderStatusFilter: String, Codable, Sendable {
    case incomplete
    case completed
    case all
}

public struct JunoRemindersListParams: Codable, Sendable, Equatable {
    public var status: JunoReminderStatusFilter?
    public var limit: Int?

    public init(status: JunoReminderStatusFilter? = nil, limit: Int? = nil) {
        self.status = status
        self.limit = limit
    }
}

public struct JunoRemindersAddParams: Codable, Sendable, Equatable {
    public var title: String
    public var dueISO: String?
    public var notes: String?
    public var listId: String?
    public var listName: String?

    public init(
        title: String,
        dueISO: String? = nil,
        notes: String? = nil,
        listId: String? = nil,
        listName: String? = nil)
    {
        self.title = title
        self.dueISO = dueISO
        self.notes = notes
        self.listId = listId
        self.listName = listName
    }
}

public struct JunoReminderPayload: Codable, Sendable, Equatable {
    public var identifier: String
    public var title: String
    public var dueISO: String?
    public var completed: Bool
    public var listName: String?

    public init(
        identifier: String,
        title: String,
        dueISO: String? = nil,
        completed: Bool,
        listName: String? = nil)
    {
        self.identifier = identifier
        self.title = title
        self.dueISO = dueISO
        self.completed = completed
        self.listName = listName
    }
}

public struct JunoRemindersListPayload: Codable, Sendable, Equatable {
    public var reminders: [JunoReminderPayload]

    public init(reminders: [JunoReminderPayload]) {
        self.reminders = reminders
    }
}

public struct JunoRemindersAddPayload: Codable, Sendable, Equatable {
    public var reminder: JunoReminderPayload

    public init(reminder: JunoReminderPayload) {
        self.reminder = reminder
    }
}
