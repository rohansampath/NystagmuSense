import SwiftUI

struct TestView: View {
    @StateObject private var vm = TestViewModel()
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            if !vm.finished {
                FadingStripeView(shade: $vm.shadeLevel)
            } else {
                Color(.systemBackground).ignoresSafeArea()
            }
            VStack(spacing: 16) {
                Text(vm.status)
                    .padding()
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                if vm.finished {
                    if let url = vm.exportURL {
                        ShareLink("Export JSON", item: url)
                    } else if vm.exportFailed {
                        Button("Retry Export") { vm.export() }
                    }
                    Button("Back") { dismiss() }
                } else {
                    Spacer()
                    Button("Cancel Recording") { vm.finish() }
                        .buttonStyle(.borderedProminent)
                }
            }
            .padding()
        }
        .task { await vm.start() }
        .onDisappear { vm.finish(reason: "View closed; recording is partial.") }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background || (vm.running && phase != .active) {
                vm.finish(reason: "App inactive; recording is partial.")
            }
        }
        .toolbar(.hidden, for: .navigationBar)
    }
}
