// swift-tools-version:5.10
// PoC 007 harness. Chunker splits contracts the way Xylo's document chunker does. Scores computes,
// for every item, the keyword score and the cosine similarity of the question to each chunk, with
// either Apple's NLEmbedding or EmbeddingGemma 300M on the llama.cpp build Xylo ships (b8901,
// through llama.swift 2.8901.0).
import PackageDescription

let package = Package(
    name: "PoC007Harness",
    platforms: [.macOS("15.0")],
    dependencies: [
        .package(url: "https://github.com/mattt/llama.swift", exact: "2.8901.0"),
    ],
    targets: [
        .executableTarget(name: "Chunker"),
        .executableTarget(
            name: "Scores",
            dependencies: [.product(name: "LlamaSwift", package: "llama.swift")]
        ),
    ]
)
