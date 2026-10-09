import Foundation

/// `ProcessInfo.ThermalState` as a stable, encodable value.
public enum ThermalState: String, Codable, Sendable, CaseIterable {
    case nominal, fair, serious, critical, unknown

    public init(_ state: ProcessInfo.ThermalState) {
        switch state {
        case .nominal: self = .nominal
        case .fair: self = .fair
        case .serious: self = .serious
        case .critical: self = .critical
        @unknown default: self = .unknown
        }
    }

    public static var current: ThermalState { ThermalState(ProcessInfo.processInfo.thermalState) }

    /// 0 (nominal) to 3 (critical). An unrecognized state ranks as `fair`.
    public var severity: Int {
        switch self {
        case .nominal: return 0
        case .fair, .unknown: return 1
        case .serious: return 2
        case .critical: return 3
        }
    }

    /// `serious` or `critical`: the states in which both apps switch to their reduced settings.
    public var isThrottled: Bool { severity >= 2 }
}
