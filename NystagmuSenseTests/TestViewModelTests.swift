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
    /// Isolated trial counter per test (never the app's real UserDefaults).
    let experiment = ExperimentLog(defaults: UserDefaults(suiteName: "vm-" + UUID().uuidString)!)

    /// Long duration so the auto-finish timer never fires during a test.
    func makeVM(now: Double = 100, startupTimeout: Double = 1000,
                uploader: RecordingUploading? = nil) -> TestViewModel {
        let vm = TestViewModel(provider: provider, duration: 1000, startupTimeout: startupTimeout,
                      outputDirectory: outputDir, uploader: { uploader }, experiment: experiment,
                      now: { now })
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

    // MARK: - Positioning (face distance)

    /// Positioning in landscape with a tracked face at `cm` for `seconds` at 60 Hz.
    func position(_ vm: TestViewModel, cm: Float?, seconds: Double, from t0: Double = 100) -> Double {
        var t = t0
        for _ in 0..<Int(seconds * 60) {
            provider.emit(cm.map { Fixture.tracked(at: t, distance: $0 / 100) } ?? .untracked(at: t))
            t += 1.0 / 60
        }
        return t
    }

    func exportedMetadata() throws -> SessionMetadata {
        let folder = try #require(exportedSessions().first)
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return try d.decode(SessionMetadata.self,
                            from: Data(contentsOf: folder.appendingPathComponent(folder.lastPathComponent + ".json")))
    }

    @Test func positioningShowsDistanceAndGatesStart() {
        let vm = makeVM()
        vm.startPositioning()
        #expect(vm.phase == .positioning)
        #expect(provider.startCount == 1)
        #expect(vm.positioning == .noFace)
        _ = position(vm, cm: 20, seconds: 0.5)
        #expect(vm.positioning == .tooClose(20))
        vm.start()
        #expect(vm.phase == .positioning)          // not ready → Start does nothing
        #expect(vm.stimulusStartTime == nil)
    }

    @Test func readyPositioningArmsRecordingWithTheSameCamera() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 200)
        vm.startPositioning()
        _ = position(vm, cm: 28, seconds: 1.2)
        #expect(vm.positioning == .ready(28))
        vm.start()
        #expect(vm.phase == .starting)
        provider.emit(Fixture.tracked(at: 200, distance: 0.28))
        #expect(vm.phase == .recording)
        provider.emit(Fixture.tracked(at: 200.5, distance: 0.42))   // drifts out: recorded, not stopped
        #expect(vm.phase == .recording)
        vm.finish()
        #expect(provider.startCount == 1)          // no second session
        let meta = try exportedMetadata()
        #expect(meta.faceDistance?.check == .passed)
        #expect(meta.faceDistance?.atStartCm.map { ($0 * 10).rounded() / 10 } == 28)
        #expect(meta.faceDistance?.fractionOutsideRange == 0.5)
    }

    @Test func bypassIsRecordedAsBypassed() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(now: 100)
        vm.startPositioning()
        provider.emit(.untracked(at: 100))
        vm.start(bypassDistanceCheck: true)
        #expect(vm.phase == .starting)
        provider.emit(Fixture.tracked(at: 100))
        vm.finish()
        #expect(try exportedMetadata().faceDistance?.check == .bypassed)
    }

    @Test func rotatingDuringPositioningReturnsToIdle() {
        let vm = makeVM()
        vm.startPositioning()
        vm.updateViewport(width: 390, height: 844)
        #expect(vm.phase == .idle)
        #expect(provider.stopCount == 1)
        #expect(vm.positioning == .noFace)
    }

    // MARK: - Trial naming

    @Test func completedRecordingsGetSequentialDescriptiveNames() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        experiment.defaults.set(TestType.pilot02.code, forKey: ExperimentLog.testTypeKey)
        for _ in 0..<2 {
            let vm = makeVM(uploader: nil)
            recordAndFinish(vm)
        }
        let names = exportedSessions().map(\.lastPathComponent).sorted()
        #expect(names.count == 2)
        #expect(names[0].hasPrefix("P02_T001_OKN_RIGHT_"))
        #expect(names[1].hasPrefix("P02_T002_OKN_RIGHT_"))
        for name in names {
            let files = try FileManager.default.contentsOfDirectory(atPath: outputDir.appendingPathComponent(name).path)
            #expect(Set(files) == [name + ".csv", name + ".json"])
        }
    }

    @Test func failedUploadDoesNotReuseTheTrialNumber() async throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        experiment.defaults.set(TestType.pilot02.code, forKey: ExperimentLog.testTypeKey)
        let first = makeVM(uploader: FakeUploader(failuresBeforeSuccess: 5))
        recordAndFinish(first)
        await first.uploadTask?.value
        guard case .failed = first.upload else { Issue.record("expected failed upload"); return }
        let second = makeVM(uploader: nil)
        recordAndFinish(second)
        let names = exportedSessions().map(\.lastPathComponent).sorted()
        #expect(names.map { String($0.prefix(8)) } == ["P02_T001", "P02_T002"])
    }

    @Test func retryExportKeepsTheSameNameAndNumber() throws {
        try Data().write(to: outputDir)
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = makeVM(uploader: nil)
        recordAndFinish(vm)
        #expect(vm.canRetryExport)
        try FileManager.default.removeItem(at: outputDir)
        vm.retryExport()
        #expect(exportedSessions().map { String($0.lastPathComponent.prefix(8)) } == ["DEV_T001"])
        #expect(experiment.nextTrialNumber == 2)
    }

    @Test func abandonedFailedExportDoesNotUseANumber() throws {
        try Data().write(to: outputDir)                 // export will fail
        let failed = makeVM(uploader: nil)
        recordAndFinish(failed)
        #expect(failed.canRetryExport)
        #expect(experiment.nextTrialNumber == 1)        // nothing was saved under T001
        try FileManager.default.removeItem(at: outputDir)
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let next = makeVM(uploader: nil)
        recordAndFinish(next)
        #expect(exportedSessions().map { String($0.lastPathComponent.prefix(8)) } == ["DEV_T001"])
    }

    @Test func switchingTestTypesContinuesOneSequenceWithoutForcingTheMode() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        experiment.defaults.set(TestType.direction.code, forKey: ExperimentLog.testTypeKey)
        recordAndFinish(makeVM(uploader: nil))
        experiment.defaults.set(TestType.fixationControl.code, forKey: ExperimentLog.testTypeKey)
        let fixVM = TestViewModel(provider: provider,
                                  stimulus: StimulusEngine(config: StimulusConfig(mode: .fixationStillStripes)),
                                  duration: 1000, outputDirectory: outputDir, uploader: { nil },
                                  experiment: experiment, now: { 100 })
        fixVM.updateViewport(width: 844, height: 390)
        recordAndFinish(fixVM)
        let names = exportedSessions().map(\.lastPathComponent).sorted()
        #expect(names.map { String($0.prefix(13)) }.sorted() == ["DIR_T001_OKN_", "FIX_T002_FIXS"])
        #expect(experiment.nextTrialNumber == 3)
    }

    @Test func cancelledOrEmptyRecordingsDoNotUseANumber() {
        let vm = makeVM()
        vm.start()
        provider.emit(Fixture.tracked(at: 100))
        vm.cancel()
        let empty = makeVM(now: 100)
        empty.start()
        provider.emit(Fixture.tracked(at: 99))      // dropped → zero samples
        empty.finish()
        #expect(experiment.nextTrialNumber == 1)
    }

    @Test func leftwardDirectionIsSavedAndNamed() throws {
        defer { try? FileManager.default.removeItem(at: outputDir) }
        let vm = TestViewModel(provider: provider,
                               stimulus: StimulusEngine(config: StimulusConfig(mode: .fixationMovingStripes,
                                                                               direction: .leftward)),
                               duration: 1000, outputDirectory: outputDir, uploader: { nil },
                               experiment: experiment, now: { 100 })
        vm.updateViewport(width: 844, height: 390)
        recordAndFinish(vm)
        let meta = try exportedMetadata()
        #expect(meta.stimulus.direction == .leftward)
        #expect(meta.recordingName?.contains("_FIXMOVE_LEFT_") == true)
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
            throw UploadError.network("simulated")
        }
    }
}
