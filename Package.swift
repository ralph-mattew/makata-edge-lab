// swift-tools-version:5.10
// Makata AI Edge Lab: reusable edge-AI components. PoCs live in poc/ and are not
// part of this package; each one has its own manifest that depends on it by path.
import PackageDescription

let package = Package(
    name: "MakataEdgeLab",
    platforms: [.macOS(.v14), .iOS(.v17)],
    products: [
        .library(name: "Instrumentation", targets: ["Instrumentation"]),
        .library(name: "EdgeRuntime", targets: ["EdgeRuntime"]),
        .library(name: "CoreMLBench", targets: ["CoreMLBench"]),
    ],
    targets: [
        .target(name: "Instrumentation"),
        .target(name: "EdgeRuntime", dependencies: ["Instrumentation"]),
        .target(name: "CoreMLBench", dependencies: ["Instrumentation"]),
        .testTarget(name: "InstrumentationTests", dependencies: ["Instrumentation"]),
        .testTarget(name: "EdgeRuntimeTests", dependencies: ["EdgeRuntime"]),
        .testTarget(name: "CoreMLBenchTests", dependencies: ["CoreMLBench", "Instrumentation"], resources: [.copy("Fixtures")]),
    ]
)
