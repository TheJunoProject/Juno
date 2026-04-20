import Foundation
import Testing
@testable import Juno

@Suite(.serialized) struct NodeServiceManagerTests {
    @Test func `builds node service commands with current CLI shape`() async throws {
        try await TestIsolation.withUserDefaultsValues(["juno.gatewayProjectRootPath": nil]) {
            let tmp = try makeTempDirForTests()
            CommandResolver.setProjectRoot(tmp.path)

            let junoPath = tmp.appendingPathComponent("node_modules/.bin/juno")
            try makeExecutableForTests(at: junoPath)

            let start = NodeServiceManager._testServiceCommand(["start"])
            #expect(start == [junoPath.path, "node", "start", "--json"])

            let stop = NodeServiceManager._testServiceCommand(["stop"])
            #expect(stop == [junoPath.path, "node", "stop", "--json"])
        }
    }
}
