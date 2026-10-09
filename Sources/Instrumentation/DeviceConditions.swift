import Foundation
#if canImport(UIKit)
import UIKit
#endif

/// Device state recorded before and after a run. Moved from
/// `unawain-public-models/benchmarks/swift/Sources/BenchCore`; the JSON shape is unchanged.
public struct DeviceConditions: Codable, Sendable {
    public var timestampUtc: String
    public var platform: String
    public var os: String
    public var osBuild: String
    public var deviceModel: String
    public var chip: String?
    public var memoryGb: Double
    public var thermalState: String
    public var lowPowerMode: Bool
    public var powerSource: String
    public var batteryLevel: Double?

    @MainActor
    public static func capture() -> DeviceConditions {
        let v = ProcessInfo.processInfo.operatingSystemVersion
        let version = "\(v.majorVersion).\(v.minorVersion).\(v.patchVersion)"
        let ts = ISO8601DateFormatter().string(from: Date())
        let memory = (Double(ProcessInfo.processInfo.physicalMemory) / 1_073_741_824 * 10).rounded() / 10
        let thermal = ThermalState.current.rawValue

        #if os(iOS)
        let device = UIDevice.current
        device.isBatteryMonitoringEnabled = true
        let power: String
        switch device.batteryState {
        case .charging: power = "charging"
        case .full: power = "full (plugged in)"
        case .unplugged: power = "battery"
        default: power = "unknown"
        }
        let level = device.batteryLevel >= 0 ? Double(device.batteryLevel) : nil
        #if targetEnvironment(simulator)
        let model = (ProcessInfo.processInfo.environment["SIMULATOR_MODEL_IDENTIFIER"] ?? "unknown") + " (Simulator)"
        #else
        let model = Sysctl.string("hw.machine") ?? "unknown"
        #endif
        return DeviceConditions(
            timestampUtc: ts, platform: "iOS", os: "\(device.systemName) \(version)",
            osBuild: Sysctl.string("kern.osversion") ?? "", deviceModel: model, chip: nil,
            memoryGb: memory, thermalState: thermal, lowPowerMode: ProcessInfo.processInfo.isLowPowerModeEnabled,
            powerSource: power, batteryLevel: level)
        #else
        let batt = shell("/usr/bin/pmset", ["-g", "batt"])
        let power = batt.contains("AC Power") ? "AC" : (batt.contains("Battery Power") ? "battery" : "unknown")
        return DeviceConditions(
            timestampUtc: ts, platform: "macOS", os: "macOS \(version)",
            osBuild: Sysctl.string("kern.osversion") ?? "", deviceModel: Sysctl.string("hw.model") ?? "unknown",
            chip: Sysctl.string("machdep.cpu.brand_string"), memoryGb: memory, thermalState: thermal,
            lowPowerMode: ProcessInfo.processInfo.isLowPowerModeEnabled, powerSource: power, batteryLevel: nil)
        #endif
    }

    public static func thermalState() -> String { ThermalState.current.rawValue }

    #if os(macOS)
    static func shell(_ path: String, _ args: [String]) -> String {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let out = Pipe()
        p.standardOutput = out
        p.standardError = FileHandle.nullDevice
        do { try p.run() } catch { return "" }
        p.waitUntilExit()
        return String(data: out.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
    }
    #endif
}

public enum Sysctl {
    public static func string(_ name: String) -> String? {
        var size = 0
        guard sysctlbyname(name, nil, &size, nil, 0) == 0, size > 0 else { return nil }
        var buf = [CChar](repeating: 0, count: size)
        guard sysctlbyname(name, &buf, &size, nil, 0) == 0 else { return nil }
        return String(cString: buf)
    }
}
