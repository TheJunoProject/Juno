// swift-tools-version: 6.2
// Package manifest for the Juno macOS companion (menu bar app + IPC library).

import PackageDescription

let package = Package(
    name: "Juno",
    platforms: [
        .macOS(.v15),
    ],
    products: [
        .library(name: "JunoIPC", targets: ["JunoIPC"]),
        .library(name: "JunoDiscovery", targets: ["JunoDiscovery"]),
        .executable(name: "Juno", targets: ["Juno"]),
        .executable(name: "juno-mac", targets: ["JunoMacCLI"]),
    ],
    dependencies: [
        .package(url: "https://github.com/orchetect/MenuBarExtraAccess", exact: "1.2.2"),
        .package(url: "https://github.com/swiftlang/swift-subprocess.git", from: "0.4.0"),
        .package(url: "https://github.com/apple/swift-log.git", from: "1.10.1"),
        .package(url: "https://github.com/sparkle-project/Sparkle", from: "2.9.0"),
        .package(url: "https://github.com/steipete/Peekaboo.git", branch: "main"),
        .package(url: "https://github.com/Blaizzy/mlx-audio-swift", exact: "0.1.2"),
        .package(path: "../shared/JunoKit"),
        .package(path: "../../Swabble"),
    ],
    targets: [
        .target(
            name: "JunoIPC",
            dependencies: [],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .target(
            name: "JunoDiscovery",
            dependencies: [
                .product(name: "JunoKit", package: "JunoKit"),
            ],
            path: "Sources/JunoDiscovery",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .executableTarget(
            name: "Juno",
            dependencies: [
                "JunoIPC",
                "JunoDiscovery",
                .product(name: "JunoKit", package: "JunoKit"),
                .product(name: "JunoChatUI", package: "JunoKit"),
                .product(name: "JunoProtocol", package: "JunoKit"),
                .product(name: "SwabbleKit", package: "swabble"),
                .product(name: "MenuBarExtraAccess", package: "MenuBarExtraAccess"),
                .product(name: "Subprocess", package: "swift-subprocess"),
                .product(name: "Logging", package: "swift-log"),
                .product(name: "Sparkle", package: "Sparkle"),
                .product(name: "PeekabooBridge", package: "Peekaboo"),
                .product(name: "PeekabooAutomationKit", package: "Peekaboo"),
                .product(name: "MLXAudioTTS", package: "mlx-audio-swift"),
            ],
            exclude: [
                "Resources/Info.plist",
            ],
            resources: [
                .copy("Resources/Juno.icns"),
                .copy("Resources/DeviceModels"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .executableTarget(
            name: "JunoMacCLI",
            dependencies: [
                "JunoDiscovery",
                .product(name: "JunoKit", package: "JunoKit"),
                .product(name: "JunoProtocol", package: "JunoKit"),
            ],
            path: "Sources/JunoMacCLI",
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
            ]),
        .testTarget(
            name: "JunoIPCTests",
            dependencies: [
                "JunoIPC",
                "Juno",
                "JunoDiscovery",
                .product(name: "JunoProtocol", package: "JunoKit"),
                .product(name: "SwabbleKit", package: "swabble"),
            ],
            swiftSettings: [
                .enableUpcomingFeature("StrictConcurrency"),
                .enableExperimentalFeature("SwiftTesting"),
            ]),
    ])
