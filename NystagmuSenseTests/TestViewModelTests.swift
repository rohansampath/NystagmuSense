//
//  TestViewModelTests.swift
//  NystagmuSenseTests
//
//  Session coordinator behaviour with a mock provider (no camera needed).
//

import Foundation
import Testing
@testable import NystagmuSense

@MainActor
struct TestViewModelTests {
    let provider = MockGazeProvider()
    let outputDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)

    /// Long duration so the auto-finish timer never fires during a test.
    func makeVM(now: Double = 100) -> TestViewModel {
        TestViewModel(provider: provider, duration: 1000, startupTimeout: 1000,
                      outputDirectory: outputDir, now: { now })
    }

    func exportedSessions() -> [URL] {
        (try? FileManager.default.contentsOfDirectory(at: outputDir, includingPropertiesForKeys: nil)) ?? []
    }

    @Test func unsupportedDeviceFailsWithoutStarting() {
        provider.isSupported = false
        let vm = makeVM()
        vm.start()
        #expect(provider.startCount == 0)
        #expect(vm.phase == .failed(GazeTrackingError.unsupportedDevice.localizedDescription))
    }

    @Test func startIsIdempotent() {
        let vm = makeVM()
        vm.start()
        vm.start()
        #expect(provider.startCount == 1)
        #expect(vm.phase == .starting)
        #expect(vm.stimulusStartTime == nil)
    }

    @Test func permissionErrorOnStartFails() {
        provider.errorOnStart = .cameraPermissionDenied
        let vm = makeVM()
        vm.start()
        #expect(vm.phase == .failed(GazeTrackingError.cameraPermissionDenied.localizedDescription))
        #expect(provider.stopCount == 1)
    }

    @Test func firstFrameStartsClockAndStimulus() {
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 99.99))
        #expect(vm.phase == .recording)
        #expect(vm.stimulusStartTime == 100)
        #expect(vm.faceTracked)
        #expect(vm.trackedCount == 0)               // first frame predates t0 → dropped
        provider.emit(Fixture.tracked(at: 100.1))
        provider.emit(.untracked(at: 100.2))
        #expect(vm.trackedCount == 1)
        #expect(!vm.faceTracked)
    }

    @Test func finishExportsExactlyOnce() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        provider.emit(Fixture.tracked(at: 100.1))
        vm.finish()
        vm.finish()

        guard case .finished(let s) = vm.phase else {
            Issue.record("expected finished, got \(vm.phase)"); return
        }
        #expect(s.sampleCount == 2)
        #expect(exportedSessions().count == 1)
        #expect(provider.stopCount == 1)
    }

    @Test func failedExportCanBeRetried() throws {
        // A regular file where the output folder should be makes the export fail.
        try Data().write(to: outputDir)
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        vm.finish()
        guard case .failed = vm.phase else {
            Issue.record("expected failed, got \(vm.phase)"); return
        }
        #expect(vm.canRetryExport)

        try FileManager.default.removeItem(at: outputDir)
        vm.retryExport()
        guard case .finished(let s) = vm.phase else {
            Issue.record("expected finished after retry, got \(vm.phase)"); return
        }
        #expect(s.sampleCount == 1)
        #expect(!vm.canRetryExport)
        #expect(exportedSessions().count == 1)
    }

    @Test func zeroSamplesIsReportedAsFailure() {
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 99.0))   // before t0 → dropped
        vm.finish()
        #expect(vm.phase == .failed(RecordingError.noSamples.localizedDescription))
        #expect(exportedSessions().isEmpty)
    }

    @Test func cancelStopsCaptureAndDiscards() {
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        vm.cancel()
        provider.emit(Fixture.tracked(at: 100.1))
        vm.finish()
        #expect(vm.phase == .cancelled)
        #expect(provider.stopCount == 1)
        #expect(exportedSessions().isEmpty)
    }

    @Test func interruptionIsNotedButRecordingContinues() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        provider.fail(.interrupted)
        #expect(vm.phase == .recording)
        provider.emit(Fixture.tracked(at: 100.2))
        vm.finish()
        guard case .finished(let s) = vm.phase else {
            Issue.record("expected finished, got \(vm.phase)"); return
        }
        #expect(s.issues == [GazeTrackingError.interrupted.localizedDescription])
    }

    @Test func leavingForegroundSavesPartialRecording() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        vm.appBecameInactive()
        guard case .finished(let s) = vm.phase else {
            Issue.record("expected finished, got \(vm.phase)"); return
        }
        #expect(s.issues == ["App left the foreground; recording is partial."])
        #expect(provider.stopCount == 1)
    }

    @Test func leavingForegroundBeforeFirstFrameFails() {
        let vm = makeVM()
        vm.start()
        vm.appBecameInactive()
        guard case .failed = vm.phase else {
            Issue.record("expected failed, got \(vm.phase)"); return
        }
        #expect(exportedSessions().isEmpty)
    }

    @Test func fatalErrorDuringRecordingSavesPartialData() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        provider.fail(.sessionFailed("boom"))
        guard case .finished(let s) = vm.phase else {
            Issue.record("expected finished, got \(vm.phase)"); return
        }
        #expect(s.sampleCount == 1)
        #expect(s.issues.count == 1)
    }
}
