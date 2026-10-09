// swift-tools-version:5.10
// PoC 003 harness. Pins the llama.cpp build Xylo ships (b8901, through llama.swift 2.8901.0).
import PackageDescription

let package = Package(
    name: "PoC003Harness",
    platforms: [.macOS(.v14)],
    dependencies: [
        .package(url: "https://github.com/mattt/llama.swift", exact: "2.8901.0"),
    ],
    targets: [
        .executableTarget(
            name: "SamplerRun",
            dependencies: [.product(name: "LlamaSwift", package: "llama.swift")]
        ),
    ]
)
