// swift-tools-version:5.10
// PoC 005 harness: PoC 003's harness plus two end-of-output interventions. Pins the llama.cpp
// build Xylo ships (b8901, through llama.swift 2.8901.0).
import PackageDescription

let package = Package(
    name: "PoC005Harness",
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
