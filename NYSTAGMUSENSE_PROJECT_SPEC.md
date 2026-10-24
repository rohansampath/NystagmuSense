NystagmuSense — Project Context, Roadmap, and Research Plan
Status: Living project brief for Rohan + collaborator, and context for Claude Code / Codex
Last updated: 2026-10-24
Repository: https://github.com/rohansampath/NystagmuSense
Research source: Rohan Sampath, Contrast Sensitivity Function Test App Using Optokinetic Nystagmus (provided as RohanSampath-InspiritResearchPaper.pdf)
Target venue: ACM ETRA 2027 short paper (aspirational; see deadlines below)
Primary principle: Get a working, inspectable experimental pipeline before expanding the architecture.

0. Read This First: Instructions for Coding Agents
You are helping improve an existing Swift/iOS app, not building a replacement from scratch. Treat this document as the project roadmap and scope reference. Only the section titled “Deliverable 1 — Today's Task” is authorized for immediate implementation unless the developer explicitly asks for later work.
Inspect the local repository, existing Xcode project, source files, and current dependencies before writing code. Do not assume a class, API, or feature exists until verified.
Preserve the working moving-grating stimulus. Prefer minimal edits to existing code over large rewrites.
Reuse an eye-tracking library already integrated into the project if present and viable. First candidate for reuse: Kyle Fox's ios-eye-tracking, referenced in the original paper. It supports sessions and JSON export, but its presence in the current project must be checked.
Avoid overengineering. No ML, deep learning, VR SDK, backend, cloud service, authentication, database migration, analytics service, or generalized plugin architecture for Deliverable 1.
Do not install additional iOS packages if built-in ARKit or an existing package suffices. For offline Python plotting, use the standard library plus matplotlib if needed. If the repo already includes a reasonable plotting tool, reuse it.
Never present simulated/mock gaze as captured human eye measurements. Clearly label real versus generated data.
Do not fabricate successful compilation, device tests, recorded data, or results. Report what was actually verified, what requires a physical iPhone, and any blockers.
Keep the first working path simple and well documented. Favor an end-to-end ten-second recording over partially implemented future architecture.
Leave the research claims appropriately cautious. This is an experimental prototype, not a validated diagnostic or medical device.
Discuss architectural changes and third-party packages only if necessary for this milestone; otherwise defer them and record them as future possibilities.
1. Executive Summary
Long-term vision: Turn NystagmuSense into a low-cost, reproducible research platform for assessing eye responses to moving, contrast-controlled visual stimuli using smartphone-based eye tracking. Eventually estimate OKN-derived contrast sensitivity, compare measurements across phone/headset configurations, and provide a reusable component for supported apps.
Current reality (reported by the project team): The moving visual stimulus works; end-to-end eye tracking and the OKN detection/heuristic pipeline do not yet work. The team currently has an iPhone, but no phone-based VR headset. A potential UCLA faculty connection may eventually help with study design, specialist equipment, data, and evaluation, but nothing is confirmed.
Immediate focus: Get real, timestamped iPhone gaze estimates while the moving stimulus is visible, automatically record for about 10 seconds, export the recording, then visualize gaze versus time in Python. Do not attempt clinical contrast scoring, OKN classification, adaptive experiments, or headset support today.
Near-term research direction: If signals are feasible, evaluate a transparent, classical signal-processing / heuristic OKN detector and the reliability of smartphone data. Machine learning is optional, not necessary. Prioritize a realistic ACM Eye Tracking Research & Applications (ETRA) short paper over a NeurIPS-oriented ML paper.
2. Background: What the App Is Supposed to Do
Optokinetic nystagmus (OKN) is an eye-movement response to moving visual patterns. It often includes:
Slow phase: eyes follow the pattern's motion.
Fast phase: eyes rapidly reset in the opposite direction.
When plotted as horizontal eye position versus time, repeated slow tracking and resets can produce a sawtooth-like pattern. Real signals can be noisy and do not always look textbook-perfect.
The original NystagmuSense concept uses moving vertical stripes/lines and varies visual contrast. If the stimulus is visible and elicits OKN, eye movements may contain a corresponding response. As visibility falls, the response may weaken or disappear. Repeating measurements under controlled conditions might allow estimation of a contrast threshold.
Important scientific distinction:
Detecting eye movement is not the same as detecting OKN.
Detecting OKN is not the same as determining a perceptual threshold.
A single contrast threshold is not a complete contrast sensitivity function (CSF). A CSF measures sensitivity at multiple spatial frequencies.
OKN-derived motion contrast sensitivity is not automatically equivalent to every established clinical contrast-sensitivity method.
Contrast sensitivity testing is not the same as visual-field perimetry; do not claim the phone simply replaces a visual-field machine.
The scientific ambition is valid as a research question, but the actual method requires careful calibration and validation.
3. What Rohan's Paper Says vs. What Works Today
3.1 Historical paper — reported methods
The original paper describes:
An iOS app using Swift/Xcode and a moving-line stimulus.
A background that changes from white toward black, decreasing the contrast of black moving bars.
Gaze tracking with Kyle Fox's iOS EyeTracking / ARKit package.
A dot-fixation experiment to compare estimated gaze locations with known screen positions.
Alignment of stimulus color values and eye measurements by timestamp.
A historical heuristic looking for certain eye-displacement magnitudes (100–150 pixels), gaps longer than one second with no events, and a log transform of a color/brightness value.
Reported preliminary repeatability and tracking observations on a small number of subjects.
Those are claims and descriptions from the earlier paper. They do not establish that the current GitHub project reproduces the results. The team specifically reports that only the stimulus is presently implemented/functioning.
3.2 What should be preserved
Existing iOS/Xcode application and its Swift UI code.
Working moving grating / vertical-line visual stimulus.
Relevant app settings and dependencies if they function.
Any useful gaze-related code already present, after inspection.
3.3 What is missing or unverified
Confirmed real-time gaze capture working with the current app.
Start/stop recording correctly synchronized with the stimulus.
Validity of eye-tracking measurements in this capture configuration.
Reliable data export and offline analysis.
OKN-specific slow/fast-phase detector and quality control.
Defensible contrast-threshold estimator and a multi-frequency CSF procedure.
Cross-device/headset measurement standardization.
Clinical or research-grade external validation.
The public README says the heuristic signaling algorithm is under development. Local code inspection is required to assess the implementation and technical debt; do not infer implementation details from the README alone.
4. Project Goals and Priorities
Goal A — Functional app (first)
A working iPhone research prototype that displays moving gratings, logs timed eye measurements, exports data, and allows a developer to inspect the results.
Goal B — Strong engineering and measurement quality (second)
A transparent OKN detection pipeline with tests, known assumptions, quality flags, latency measurements, and reproducible data processing.
Goal C — Academic research publication (third, pursued alongside engineering)
Submit evidence-based work to a relevant eye-tracking venue, provisionally ETRA 2027 short papers. A paper must contribute a credible measurement method, comparison, empirical finding, validated protocol, or useful research artifact—not just a functional app.
Goal D — Standardization across phones/headsets (longer term)
Create a device-calibrated interface for multiple supported phone models, viewing distances, display geometries, and VR headset configurations. Portability must be tested, not assumed.
Goal E — Possible eventual clinical collaboration
Work with Cornell/UCLA investigators if available for study design, reference equipment, and human-participant research. Do not claim clinical diagnostic accuracy before appropriate evaluation.
Explicit deprioritization
NeurIPS and a novel ML method are not project requirements.
Training a CNN, TCN, transformer, or domain adaptation system is a possible future experiment, not current work.
A general-purpose SDK and arbitrary third-party app integration are stretch goals.
Headset integration is not a prerequisite to developing the phone-only prototype.
5. Deliverable 1 — TODAY'S TASK (only immediate implementation scope)
Record ten seconds of timestamped gaze estimates on an actual iPhone while the moving grating remains displayed; export the measurements; plot the gaze trace over time in Python.
This is a feasibility / instrumentation experiment, not yet OKN detection.
5.1 Expected user flow
Open the existing iOS app on a physical supported iPhone.
Tap a simple Start Recording / Start Test control (reuse the existing button if appropriate).
The existing moving grating is shown throughout the recording.
Eye-tracking samples begin, and recording duration is about 10 seconds.
Recording stops automatically (and ideally can be cancelled safely).
The app reports whether tracking was supported / permission was granted and the number of samples actually recorded.
Export the captured session to a local JSON or CSV file accessible through iOS share/export or another straightforward existing export mechanism.
Copy the file to a Mac, run one documented Python command, and view a PNG chart showing eye position against time.
5.2 Minimum recorded information
Prefer the existing library's native export schema rather than inventing another format. At minimum, recording/analysis must be able to recover:
A real timestamp per eye-tracking sample, not an assumed uniform frame rate.
Horizontal gaze estimate (x) and, if readily available, vertical estimate (y).
Sample units and coordinate reference (e.g. screen points or pixels), documented accurately; do not label values degrees unless actually calibrated.
Session start/end times and source device/model when available.
Validity indicators or tracking failures if the API exposes them. Do not silently invent confidence scores.
A marker of when the moving stimulus started and ended, if feasible without substantial refactoring. For actual stimulus-response alignment later, use a consistent clock or explicitly synchronize clocks; do not claim exact alignment until verified.
Optional: direction and fixed speed/contrast parameters used for that session.
If the gaze library already exports beginTime, endTime, scanPath with timestamp, x, y, and deviceInfo, keep that native shape and make the Python plotter parse it.
5.3 Python plotting script
Add the smallest script possible, for example scripts/plot_gaze.py:
Accept an exported recording file as a CLI argument.
Parse the actual file structure written by the app.
Convert timestamps to elapsed seconds relative to the beginning of the data.
Plot x vs. time; optionally y vs. time, as a second series or panel.
Label the axes with the actual units.
Save a PNG, optionally show the plot when run interactively.
Print sample count, covered duration, approximate actual sampling rate, and missing/invalid measurements where data supports these metrics.
Exit with a clear error if the file has no valid gaze samples.
Do not smooth, fabricate, interpolate, or classify the data for this first plot.
One permitted Python dependency is matplotlib. Everything else should ideally be Python standard library. If an existing repo plotting tool already accomplishes this, reuse it.
5.4 Definition of done / acceptance criteria
Existing grating still renders and moves as before.
Recording session automatically stops at about 10 seconds without crashing.
On a supported device with permission, real nonempty gaze measurements are actually stored.
Recorded sample timestamps are present and monotonically nondecreasing/ordered after extraction.
Exported file can be obtained from the phone using clear steps.
python scripts/plot_gaze.py <session-file> (or documented equivalent) produces a chart from the real file.
Chart shows x-position versus actual elapsed time, not merely sample index.
App reports unsupported tracking, permission denial, zero samples, or export failures honestly rather than showing fake success.
A short README section documents setup, how to record/export, how to run the plotter, known limitations, and what was physically tested.
Do not call this successful until someone has verified an exported session containing actual device measurements. Compilation, a JSON fixture, or simulator-only testing may validate components but are not sufficient.
5.5 Important feasibility constraints
Test ARKit face tracking compatibility on the actual device, using the platform's support checks. Test camera permission handling.
Use actual callback/sample timestamps; a nominal library rate (such as a documented 60 fps) is not a guaranteed observed rate.
A phone's front camera usually requires an appropriate camera-to-face geometry. A future VR headset may obstruct the camera and invalidate this approach; headset feasibility remains open.
If eyes are not detected, investigate front-camera distance, phone orientation, lighting, app lifecycle, and API requirements before adding more software packages.
If the SDK's session handling or export is broken, make a focused fix rather than introducing a new data platform.
Use the existing simulator only for app logic/UI checks, not as evidence of human gaze capture.
5.6 Preferred implementation order for the coding agent
Audit repo structure, existing app entry point, stimulus view, installed packages, Info.plist, target iOS versions, and any gaze/session code.
Identify the simplest usable gaze data source—reuse existing Kyle Fox EyeTracking if integrated/working; otherwise consider built-in ARKit before adding a dependency.
Wire session begin/end to existing test control and ~10-second duration; keep stimulus running during collection.
Export native gaze session data as a local file. Ensure sample count or emptiness is visible.
Write minimal scripts/plot_gaze.py for the exact exported format.
Run checks possible in the environment; explicitly flag any remaining Xcode/physical-device manual test steps.
Report changed files, design decisions, any actual test results, and exactly what the developer should do next on the iPhone.
5.7 Out of scope TODAY
OKN detection or start/stop heuristics.
Savitzky–Golay, Kalman filters, trained classifiers, or other denoising pipelines.
Estimating contrast thresholds, log contrast sensitivity, or clinical scores.
Adaptive psychophysical testing, per-eye diagnosis, or CSF fitting.
Headsets, Android, Unity, reusable SDK packaging, new rendering engines.
Cloud backends, accounts, user databases, dashboards, CI infrastructure.
Academic human-subject data collection beyond appropriate engineering tests.
6. Implementation Stack: Minimal Now, Extensible Later
Use now
Swift / existing Xcode project — preserve current implementation.
Existing grating stimulus — do not rewrite the renderer without evidence it is broken.
Apple ARKit face/eye tracking via existing code/library — test compatibility.
Kyle Fox ios-eye-tracking (only if already integrated or the easiest justified reuse) — provides recording sessions and JSON export; original paper references it. Source: https://github.com/kyle-fox/ios-eye-tracking
Python 3 + matplotlib — visualize exported samples.
Git/GitHub — issues, commits, experiment notes.
Candidate tools later (not automatic dependencies)
pymovements: https://github.com/pymovements/pymovements — eye-movement preprocessing/event analysis.
REMoDNaV: https://github.com/psychoinformatics-de/remodnav — event-detection baseline.
PyOKR: https://pypi.org/project/PyOKR/ — literature-related optokinetic response analysis; requires suitability checks for phone data.
FaceTrackingKit: https://github.com/digital-medicine/FaceTrackingKit — alternative gaze/face capture integration to investigate if necessary.
SciPy / NumPy: for later offline signal processing and estimation, not necessary for Deliverable 1.
Do not adopt a package based only on this list; inspect licenses, maintenance, exact API, hardware requirements, and relevance first.
7. Planned OKN Analysis After Deliverable 1
These are candidate algorithms, not code that exists yet.
7.1 Classical interpretable baseline
Read actual timestamped horizontal gaze samples.
Mark invalid samples, blinks, dropped measurements, and discontinuities.
Convert gaze to interpretable units through calibration if possible.
Smooth/differentiate cautiously (e.g. a short Savitzky–Golay differentiator, evaluated against alternatives) to estimate eye velocity.
Identify slow phases moving with the grating and rapid counter-direction resets.
Produce trial/window-level OKN evidence such as slow-phase velocity gain, directional consistency, and valid event counts.
Require evidence sustained over a window; use a state machine with hysteresis to avoid chattering at the detection boundary.
Return detected / not detected / insufficient signal quality, not a forced binary decision for every recording.
7.2 How to define “start” and “stop”
NOT_TRACKING -> TRACKING only when OKN evidence exceeds an entry threshold for a sustained interval.
TRACKING -> NOT_TRACKING only when evidence stays below a lower exit threshold for a sustained interval.
Distinguish true loss of tracking from loss of usable eye measurements; do not interpret closed eyes or camera dropout as a perceptual threshold.
Time-window lengths, velocity thresholds, and quality cutoffs must be tuned on measured data rather than asserted as universal physiological constants.
Do not use Pearson correlation against a strictly constant stimulus velocity signal; it has no variance and ordinary correlation is not informative. Instead use signed velocity gain/directional consistency, or time-varying motion sequences with proper stimulus-response analysis.
7.3 What needs careful validation
Fast reset phases may be undersampled by low frame rates.
Position estimation errors can dominate small eye movements.
Device-specific camera noise, head movement, blink handling, and timestamp jitter can create false positive events.
Head and eye geometry affect mapping from gaze estimates to visual angles.
No single heuristic should be called medically validated without comparative data.
8. Planned Contrast-Sensitivity Testing — After OKN Detection
The original stimulus fades a light background while keeping black stripes. This changes mean luminance as well as contrast, which can confound threshold interpretation.
A better research protocol to investigate is drifting sinusoidal or bar gratings at calibrated spatial frequencies and controlled mean luminance. A standard contrast definition for periodic patterns is Michelson contrast:
C = (L_max - L_min) / (L_max + L_min)
Estimate a contrast threshold from multiple trials rather than taking the first apparent moment OKN stops. If justified by psychophysical assumptions and validated against standards:
contrast sensitivity = 1 / threshold contrast
Repeat over multiple spatial frequencies to estimate a CSF curve. Calibration will have to account for display luminance/gamma, pixel density, eye-to-display geometry, motion speed, and viewing conditions.
Potential later enhancement: an established adaptive threshold method such as QUEST+ or Bayesian adaptive experiment selection to shorten test time and quantify uncertainty. Use classical adaptive estimation before considering reinforcement learning.
9. Standardization Across Devices / Headsets / Apps (Stretch Goal)
User intent: Eventually support different phones and phone-based VR headsets. A reusable SDK for other supported applications is an additional ambition.
What “standardization” actually requires
A device/session profile containing, where available:
Phone model, OS version, camera capability, effective sample rate.
Display size, pixel resolution, pixel density, brightness/color settings and measured calibration.
Viewing distance and headset geometry; lens distortion/FOV when relevant.
Gaze-coordinate convention, units, timestamp convention, and transformation/calibration method.
Stimulus parameters: spatial frequency (cycles/degree once calibrated), speed (degrees/second once calibrated), direction, contrast, duration.
Quality metrics: valid sample fraction, missing intervals, reliability of calibration.
Proposed future modular interfaces
StimulusEngine — rendering + parameter/timing metadata.
GazeProvider — normalized gaze samples from ARKit, another smartphone system, or external eye tracker.
SessionRecorder — durable timestamped data and export.
OKNDetector — offline/online classification, validity and confidence.
ThresholdEstimator — adaptive contrast trials and uncertainty.
DeviceProfile — device geometry and calibration.
Do not build these abstractions wholesale for Deliverable 1. Introduce interfaces only when multiple actual backends or uses justify them.
Key platform/hardware risks
A phone placed directly in a VR holder may obstruct or misorient the front-facing TrueDepth camera.
Even if gaze estimation works with a normally held phone, it may fail inside the headset.
iOS apps cannot assume they can read camera data while arbitrary unrelated apps are foregrounded. A reusable library should target applications that explicitly integrate it, not a universal OS-wide overlay.
Different device setups need experimental cross-device evaluation, not only code compatibility.
10. Research Plan — ETRA Rather Than NeurIPS
10.1 Preferred publication framing
Provisional title: Toward Low-Cost Smartphone-Based Optokinetic Nystagmus Measurement: Feasibility, Detection, and Reproducibility
Do not promise the title's implied results in advance. A narrower, well-evidenced feasibility/benchmark paper is better than an overclaimed generalization or clinical-validation paper.
Potential research questions, in order:
Can a commodity iPhone record usable gaze signals during a standardized moving-grating experiment?
Can a straightforward, interpretable OKN detector distinguish induced response from common artifacts and nonresponse?
How do sampling quality, viewing distance, movement direction, lighting, and participant effects change detection reliability?
Are repeated measurements from the same device/person consistent?
If multiple devices become available, how much calibration is needed to generalize measurement across them?
If collaborators provide reference instruments, how do the smartphone estimates agree with research-grade equipment and established vision tests?
10.2 Proposed evaluation metrics (later)
Gaze data capture: actual sampling frequency, dropped sample proportion, usable segment duration, latency/jitter.
OKN classification: sensitivity/recall, specificity, precision, F1, false positive rate, confidence intervals.
Signal processing: slow-phase gain and direction agreement, timing uncertainty, artifacts.
Repeatability: within-subject/test–retest variability and agreement rather than only close-looking numerical outputs.
Device effects: calibration error and performance under held-out hardware configurations if enough devices are available.
Threshold estimation: repeatability, psychometric fitting uncertainty, and agreement with a selected reference method.
10.3 Baselines to compare
A simple directional velocity threshold heuristic.
A published/established event-detection approach adapted appropriately to the recorded sampling regime.
A quality-aware, phase-based detector only if experiments motivate it.
Any model or improvement must be judged against these baselines on actual data and against human/reference labels where feasible.
10.4 Proposed experiments (dependent on permissions/resources)
Engineering feasibility: check signal integrity and simple task changes on the developers' own setup.
Direction reversal: does horizontal response direction change appropriately when motion reverses?
No-motion or low-contrast control: does the detector abstain or avoid inappropriate positive detections?
Repeated sessions under controlled conditions to investigate reliability.
Different phone/headset geometry if real hardware is available.
Expert annotated/reference gaze recordings if UCLA/Cornell investigators collaborate.
Human-subject research: Seek the institution's appropriate IRB determination/approval before recruiting participants or treating testing as publishable participant research. Establish informed consent, data governance, anonymization, and a minimally sufficient data policy. Ordinary developer debugging is not a substitute for a research protocol.
10.5 Conference timing (verified on official ETRA 2027 CFP)
ETRA 2027 short-paper abstract due: 2027-02-04 (mandatory, Anywhere on Earth).
ETRA 2027 short-paper due: 2027-02-11 (Anywhere on Earth).
ETRA conference: 2027-06-07 through 2027-06-10 in Pamplona, Spain.
2027 full-paper deadlines (2026-10-09 abstract / 2026-10-16 paper) have already passed as of this brief.
Official CFP: https://etra.acm.org/2027/cfp.html
Meeting the short-paper deadline is aspirational. Submission is only sensible if there is adequate, ethically collected evidence and a clear research contribution; otherwise target another workshop/venue or a later cycle.
10.6 UCLA / Cornell academic collaboration
Potential UCLA connections are unconfirmed. Valuable requests include:
Feedback on scientific validity of the OKN protocol.
Access to high-quality reference eye tracking / video-oculography.
Expert eye-movement annotations or suitable shareable datasets.
Access to or advice about reference contrast-sensitivity assessment.
IRB/study design and realistic sample-size considerations.
Mentorship on paper framing and evidence standards.
Do not make today’s deliverable depend on any of these connections.
11. Timeline / Milestone Sequence
M0 — Today: Instrumentation feasibility. Ten seconds of real gaze data while grating moves; export + raw Python plot.
M1 — Next: Reproducible signal capture. Fix session lifecycle, sample validity, event timestamps, basic repeated recordings, and obvious integration bugs. Run a basic fixation/known-point calibration sanity check if relevant.
M2 — Classical OKN detector. Build simple offline preprocessing and baseline event detection with diagnostic plots and quality rejection.
M3 — Controlled contrast trials. Introduce scientifically justified contrast/grating settings, repeated randomized trials, and a preliminary threshold model.
M4 — Research benchmark. Define reference labels and experimental conditions; evaluate failures, repeatability, and baselines with appropriate approvals.
M5 — Paper. Write methods and results based on real measured evidence; target ETRA short-paper submission if credible and ready.
M6 — Optional hardware portability. Add a second phone, then evaluate headset compatibility. Only add a hardware-agnostic gaze interface when needed.
M7 — Optional longer-range platform. Multi-device library/SDK, integration with other cooperating apps, and expanded clinical comparisons.
No commitment to deliver all milestones by the same date; external hardware and research approvals are dependencies.
12. Stretch Goals / Idea Bank (Do Not Implement Now)
Research and signal-processing
Better slow-/fast-phase segmentation and robust velocity estimation.
Online state machine with hysteresis and tracking-quality abstention.
Confidence intervals and calibrated uncertainty for threshold estimates.
Adaptive visual-stimulus selection (e.g. QUEST+).
Controlled monocular vs binocular measurement, with appropriate optics and protocol.
Multi-frequency CSF estimation with calibrated luminance and spatial frequency.
Gaze replay, experiment session explorer, and automated benchmark reports.
Portability and product engineering
Multiple iPhone models with per-device calibration profiles.
Phone-based VR configurations with correct lens and camera geometry.
External inward-facing camera and infrared eye-tracking support, if required by headset physics.
Android capture backend (only after iPhone proof of feasibility).
Swift Package or Unity integration for consenting, cooperating third-party apps.
Reusable standardized timestamped gaze + stimulus dataset format.
Offline-first privacy-aware experimental data management.
Optional ML/AI research (explicitly deferred)
None of the following is required to produce a valuable ETRA paper:
A 1D CNN/TCN to classify eye-movement windows.
Stimulus-conditioned sequence classification using both motion command and measured gaze.
Quality estimation / selective prediction: explicitly abstain when unreliable.
Domain adaptation across phones or subjects, evaluated on held-out devices.
Few-shot personalized calibration for a new subject/device.
Pretrained gaze estimation if native gaze capture proves inadequate.
Bayesian optimization / RL for adaptive testing only if classical psychophysics baselines are insufficient and a clear measurable improvement exists.
Warning: These add annotation, dataset, validation, compute, and scope costs. They are not automatically novel or necessary.
13. Risks and Decision Gates
Risk
Consequence
Immediate response
Current camera/ARKit tracking fails on available iPhone
No real eye traces
Check compatibility, permissions, device orientation, lighting, and package lifecycle before expanding scope
Sampled gaze too noisy/low-frequency
OKN phases may be unrecoverable
Report the signal limitation honestly; experiment with geometry, alternative gaze backends, or reference equipment
Library/old app crashes or export fails
Can't inspect experiments
Fix the smallest data path; preserve stimulus
No headset yet
Can't claim VR compatibility
Continue with phone-only feasibility; defer VR generalization
One available phone
No cross-device evidence
Avoid cross-device generalization claims
Mean luminance changes with contrast
Confounded threshold estimates
Redesign and calibrate controlled grating stimuli in a later milestone
No participant study approval/data
Weak publication evidence
Get academic supervision and review requirements early; limit claims
No UCLA equipment access
No external clinical validation
Publish only claims supported by feasible internal research, or adjust venue/timing
Scope creep from ML, SDK, UI
Delayed first measurement
Enforce Deliverable 1 out-of-scope list

Hard decision gate: If a real, valid gaze trace cannot be collected with the available phone and app, prioritize investigating sensing feasibility. Do not invest in more complex detection or clinical-scoring features until that blocker is understood.
14. Research Integrity and Safety
Do not market or label the app as a validated clinical diagnostic device at this stage.
Avoid suggesting the app can diagnose glaucoma, neurodegenerative disease, or replace a standard clinical visual-field test.
Protect biometric/face/eye data. Prefer exporting derived gaze coordinates, avoid retaining identifiable camera video by default, and document privacy controls.
Report study size, hardware versions, recording conditions, missed samples, uncertainty, and failure cases.
Never convert developer debugging into claimed participant-study evidence without the required ethics process.
15. Relevant Sources and Further Reading
Project:
Repository and README: https://github.com/rohansampath/NystagmuSense
Rohan Sampath, Contrast Sensitivity Function Test App Using Optokinetic Nystagmus, original supplied PDF (historical methods and preliminary claims, not independently verified).
Kyle Fox iOS EyeTracking: https://github.com/kyle-fox/ios-eye-tracking
Research:
Essig et al. (2021), Contrast Sensitivity Testing in Healthy and Blurred Vision Conditions Using a Novel Optokinetic Nystagmus Live-Detection Method: https://pmc.ncbi.nlm.nih.gov/articles/PMC8496416/
EyePhone (2024), smartphone-based nystagmus research: https://pmc.ncbi.nlm.nih.gov/articles/PMC10926800/
PyOKR paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC11187712/
ACM ETRA 2027 CFP and requirements: https://etra.acm.org/2027/cfp.html
Coding-agent final instruction: When implementing Deliverable 1, inspect and modify the actual repository. Make the smallest functional changes, provide a usable plotting script, and finish with exact Xcode/iPhone test instructions and a truthful report of what is and is not verified. Do not implement the remainder of this document unless separately asked.
