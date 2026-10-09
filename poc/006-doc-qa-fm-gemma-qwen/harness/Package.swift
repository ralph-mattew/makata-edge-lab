// swift-tools-version:5.10
// PoC 006 harness. GGUFQA runs Gemma and Qwen through Xylo's chat generation loop on the llama.cpp
// build Xylo ships (b8901, through llama.swift 2.8901.0). FMQA runs Apple's on-device
// FoundationModels with Xylo's chat options.
import PackageDescription

let package = Package(
    name: "PoC006Harness",
    platforms: [.macOS("26.4")],
    dependencies: [
        .package(url: "https://github.com/mattt/llama.swift", exact: "2.8901.0"),
    ],
    targets: [
        .executableTarget(
            name: "GGUFQA",
            dependencies: [.product(name: "LlamaSwift", package: "llama.swift")]
        ),
        .executableTarget(name: "FMQA"),
    ]
)
