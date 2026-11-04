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
    func makeVM(now: Double = 100, startupTimeout: Double = 1000,
                uploader: RecordingUploading? = nil) -> TestViewModel {
        let vm = TestViewModel(provider: provider, duration: 1000, startupTimeout: startupTimeout,
                      outputDirectory: outputDir, uploader: { uploader }, now: { now })
        vm.updateViewport(width: 844, height: 390)
        return vm
    }

    @Test func portraitCannotStartCameraOrStimulus() {
        let vm = makeVM()
        vm.updateViewport(width: 390, height: 844)
        vm.start()
        #expect(vm.phase == .idle)
        #expect(provider.startCount == 0)
        #expect(vm.stimulusStartTime == nil)
        vm.updateViewport(width: 844, height: 390)
        vm.start()
        #expect(provider.startCount == 1)
        #expect(vm.phase == .starting)
    }

    @Test func unknownViewportCannotStart() {
        let vm = TestViewModel(provider: provider)
        vm.start()
        #expect(vm.phase == .idle)
        #expect(provider.startCount == 0)
    }

    @Test func untrackedFramesDoNotStartStimulus() {
        let vm = makeVM()
        vm.start()
        provider.emit(.untracked(at: 100))
        #expect(vm.phase == .starting)
        #expect(vm.stimulusStartTime == nil)
        provider.emit(Fixture.tracked(at: 100))
        #expect(vm.phase == .recording)
    }

    @Test func rotationBeforeFirstFrameReturnsToReadiness() {
        let vm = makeVM()
        vm.start()
        vm.updateViewport(width: 390, height: 844)
        provider.emit(Fixture.tracked(at: 100))
        #expect(vm.phase == .idle)
        #expect(provider.stopCount == 1)
        #expect(vm.stimulusStartTime == nil)
    }

    @Test func rotationDuringRecordingSavesPartialWithOriginalGeometry() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM()
        vm.start()
        provider.emit(Fixture.tracked(at: 100))
        vm.updateViewport(width: 390, height: 844)
        provider.emit(Fixture.tracked(at: 100.1))
        guard case .finished(let summary) = vm.phase else {
            Issue.record("expected finished, got \(vm.phase)"); return
        }
        #expect(summary.sampleCount == 1)
        #expect(summary.issues == ["Stimulus surface changed size or orientation; recording is partial."])
        #expect(provider.stopCount == 1)
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        let metadata = try decoder.decode(SessionMetadata.self, from: Data(contentsOf: summary.files.metadata))
        #expect(metadata.stimulusViewport == StimulusViewport(widthPoints: 844, heightPoints: 390))
        #expect(metadata.stimulus.stripeGray == 0)
        #expect(metadata.stimulus.fixedBackgroundGray == nil)
        #expect(metadata.stimulus.fadeHalfCycleSeconds == 10)
        #expect(metadata.stimulus.speedPointsPerSecond == 126)
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

    @Test func inactiveDuringRecordingSavesPartialRecording() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        vm.scenePhaseChanged(.inactive)
        guard case .finished(let s) = vm.phase else {
            Issue.record("expected finished, got \(vm.phase)"); return
        }
        #expect(s.issues == ["App left the foreground; recording is partial."])
        #expect(provider.stopCount == 1)
    }

    /// ARKit's first-run camera-permission alert makes the scene inactive.
    @Test func cameraPermissionAlertDoesNotFailStartup() {
        let vm = makeVM(now: 100)
        vm.start()
        vm.scenePhaseChanged(.inactive)
        #expect(vm.phase == .starting)
        #expect(provider.stopCount == 0)
        vm.scenePhaseChanged(.active)
        provider.emit(Fixture.tracked(at: 100))
        #expect(vm.phase == .recording)
    }

    @Test func backgroundingBeforeFirstFrameReturnsToReadiness() {
        let vm = makeVM()
        vm.start()
        vm.scenePhaseChanged(.background)
        #expect(vm.phase == .idle)
        #expect(provider.stopCount == 1)
        #expect(exportedSessions().isEmpty)
        vm.start()
        #expect(provider.startCount == 2)
    }

    @Test func noCameraFramesTimesOutAsNoFrames() async throws {
        let vm = makeVM(startupTimeout: 0.05)
        vm.start()
        try await Task.sleep(for: .milliseconds(300))
        #expect(vm.phase == .failed(GazeTrackingError.noFramesReceived.localizedDescription))
    }

    @Test func framesWithoutFaceTimeOutAsNoTrackedFace() async throws {
        let vm = makeVM(startupTimeout: 0.05)
        vm.start()
        provider.emit(.untracked(at: 100))
        try await Task.sleep(for: .milliseconds(300))
        #expect(vm.phase == .failed(GazeTrackingError.noTrackedFace.localizedDescription))
    }

    @Test func permissionAlertPausesNoFramesTimeout() async throws {
        let vm = makeVM(startupTimeout: 0.05)
        vm.start()
        vm.scenePhaseChanged(.inactive)
        try await Task.sleep(for: .milliseconds(300))
        #expect(vm.phase == .starting)
        vm.scenePhaseChanged(.active)
        try await Task.sleep(for: .milliseconds(300))
        #expect(vm.phase == .failed(GazeTrackingError.noFramesReceived.localizedDescription))
    }

    @Test func failedStartCanBeTriedAgain() {
        provider.errorOnStart = .cameraPermissionDenied
        let vm = makeVM()
        vm.start()
        #expect(vm.canTryAgain)
        provider.errorOnStart = nil
        vm.tryAgain()
        #expect(vm.phase == .idle)
        #expect(vm.stimulusStartTime == nil && vm.trackedCount == 0)
        vm.start()
        #expect(provider.startCount == 2)
        #expect(vm.phase == .starting)
    }

    @Test func failedExportOffersRetryNotTryAgain() throws {
        try Data().write(to: outputDir)
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        vm.finish()
        #expect(vm.canRetryExport)
        #expect(!vm.canTryAgain)
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

    // MARK: - Mac upload

    /// Records one sample and finishes, leaving the VM in `.finished`.
    func recordAndFinish(_ vm: TestViewModel) {
        vm.start()
        provider.emit(Fixture.tracked(at: 100.0))
        vm.finish()
    }

    @Test func notConfiguredMeansSavedLocallyOnly() {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(uploader: nil)
        recordAndFinish(vm)
        #expect(vm.upload == .notConfigured)
        #expect(exportedSessions().count == 1)
    }

    @Test func uploadsBothFinalizedFilesAfterLocalSave() async throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let uploader = FakeUploader()
        let vm = makeVM(uploader: uploader)
        recordAndFinish(vm)
        #expect(vm.upload == .uploading)
        await vm.uploadTask?.value
        #expect(vm.upload == .uploaded)
        guard case .finished(let s) = vm.phase else { Issue.record("expected finished"); return }
        #expect(uploader.uploaded == [s.files])
        #expect(uploader.sawFilesOnDisk)
        // The local copy is kept after a successful upload.
        #expect(FileManager.default.fileExists(atPath: s.files.csv.path))
        #expect(FileManager.default.fileExists(atPath: s.files.metadata.path))
    }

    @Test func failedUploadKeepsLocalRecordingAndCanBeRetried() async throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let uploader = FakeUploader(failuresBeforeSuccess: 1)
        let vm = makeVM(uploader: uploader)
        recordAndFinish(vm)
        await vm.uploadTask?.value
        guard case .failed = vm.upload else { Issue.record("expected failed upload, got \(String(describing: vm.upload))"); return }
        guard case .finished(let s) = vm.phase else { Issue.record("expected finished"); return }
        #expect(FileManager.default.fileExists(atPath: s.files.csv.path))
        #expect(FileManager.default.fileExists(atPath: s.files.metadata.path))
        #expect(!vm.canRetryExport)

        vm.retryUpload()
        await vm.uploadTask?.value
        #expect(vm.upload == .uploaded)
        #expect(uploader.uploaded == [s.files, s.files])
        #expect(exportedSessions().count == 1)
    }

    @Test func retryUploadDoesNothingUnlessUploadFailed() async {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let uploader = FakeUploader()
        let vm = makeVM(uploader: uploader)
        recordAndFinish(vm)
        await vm.uploadTask?.value
        vm.retryUpload()
        await vm.uploadTask?.value
        #expect(uploader.uploaded.count == 1)
    }

    @Test func failedExportUploadsNothingUntilRetryExportSucceeds() async throws {
        try Data().write(to: outputDir)
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let uploader = FakeUploader()
        let vm = makeVM(uploader: uploader)
        recordAndFinish(vm)
        #expect(vm.upload == nil)
        #expect(uploader.uploaded.isEmpty)

        try FileManager.default.removeItem(at: outputDir)
        vm.retryExport()
        await vm.uploadTask?.value
        #expect(vm.upload == .uploaded)
        #expect(uploader.uploaded.count == 1)
    }
}

/// Test-only uploader: fails a set number of times, then succeeds.
final class FakeUploader: RecordingUploading {
    private var failuresLeft: Int
    private(set) var uploaded: [RecordingFiles] = []
    private(set) var sawFilesOnDisk = false

    init(failuresBeforeSuccess: Int = 0) { failuresLeft = failuresBeforeSuccess }

    func upload(_ files: RecordingFiles) async throws {
        uploaded.append(files)
        sawFilesOnDisk = FileManager.default.fileExists(atPath: files.csv.path)
            && FileManager.default.fileExists(atPath: files.metadata.path)
        if failuresLeft > 0 {
            failuresLeft -= 1
            throw UploadError.unreachable("simulated")
        }
    }
}
