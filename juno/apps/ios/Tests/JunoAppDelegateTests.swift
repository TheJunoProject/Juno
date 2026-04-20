import Testing
@testable import Juno

@Suite(.serialized) struct JunoAppDelegateTests {
    @Test @MainActor func resolvesRegistryModelBeforeViewTaskAssignsDelegateModel() {
        let registryModel = NodeAppModel()
        JunoAppModelRegistry.appModel = registryModel
        defer { JunoAppModelRegistry.appModel = nil }

        let delegate = JunoAppDelegate()

        #expect(delegate._test_resolvedAppModel() === registryModel)
    }

    @Test @MainActor func prefersExplicitDelegateModelOverRegistryFallback() {
        let registryModel = NodeAppModel()
        let explicitModel = NodeAppModel()
        JunoAppModelRegistry.appModel = registryModel
        defer { JunoAppModelRegistry.appModel = nil }

        let delegate = JunoAppDelegate()
        delegate.appModel = explicitModel

        #expect(delegate._test_resolvedAppModel() === explicitModel)
    }
}
