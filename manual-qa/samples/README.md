# Manual QA Samples

All files here are originally authored, synthetic content created for this
QA baseline. None of it is real user data, and none of it is copyrighted
third-party media. See "Privacy provenance" at the bottom.

## subtitles/normal_lesson.srt / normal_lesson.vtt

- **Format:** SRT and WebVTT versions of the same 10-cue, ~28-second content
  (a short, generic two-person dialogue about greetings/coffee/plans —
  invented for this purpose, no real-world source).
- **Tests:** the normal/happy-path import, playback, transcript workspace,
  guided session, quiz, shadowing, Quick Practice, Learning History, and
  export workflows (Modules 01-10).
- **Expected result:** imports cleanly in both formats; both should parse to
  the same 10 cues with the same timings and text.
- **Use with:** `audio/normal_lesson.wav` (paired 1:1 by matching duration
  and cue timings).

## audio/normal_lesson.wav

- **Format:** mono, 16-bit PCM WAV, 8000 Hz, 28.0 seconds — generated with
  Python's standard-library `wave` module (no proprietary codec, no
  copyrighted recording).
- **Content:** silence, with a short sine-wave beep (rising in pitch,
  440 Hz + 40 Hz per cue) placed at the start of each of
  `normal_lesson.srt`'s 10 cues, so a tester can audibly cross-check that
  the highlighted transcript cue matches the actual playback position.
- **Expected result:** loads and plays through the packaged Qt Multimedia
  (FFmpeg) backend exactly like any real recording would.

## subtitles/boundary_stress.srt

- **Format:** SRT, 7 cues, ~45 seconds total.
- **Content, each cue deliberately at an edge:** an 80ms cue (minimum
  practical duration); a very long line mixing Chinese, English, and
  punctuation (line-wrap stress); a cue mixing emoji with CJK and English;
  an unusually long 30-second cue (looping/replay stress); two adjacent
  cues with identical (Chinese) text (duplicate-content stress); a line with
  angle brackets, quotes, apostrophes, and a backslash (special-character
  stress).
- **Tests:** subtitle parsing/line-wrap robustness, Unicode-offset-safe
  annotation over emoji/CJK, long- and short-cue looping/navigation
  (Module 02), and cue-list scrolling under content stress (Module 13).
- **Use with:** `audio/normal_lesson.wav` reused deliberately — its 28s
  duration is shorter than this subtitle's 45s, which is itself a boundary
  case ("subtitle duration exceeds media duration", exercised in Module 01).
- **Expected result:** imports without crashing; the app's actual handling
  of the duration mismatch is exactly what Module 01's checklist item asks
  you to observe and record, not a predetermined pass/fail.

## subtitles/invalid_non_numeric_index.srt, invalid_timing_backwards.srt, invalid_missing_webvtt_header.vtt

- **Format:** minimal single-cue files, each broken in exactly one way
  (non-numeric SRT index; end timestamp earlier than start timestamp;
  a `.vtt` file missing its required `WEBVTT` header).
- **Provenance:** copied unchanged from the project's own automated-test
  fixtures (`tests/fixtures/subtitles/malformed_*`), reused here rather than
  duplicated with new content, per this baseline's "reuse existing fixtures
  when they're already sufficient" rule.
- **Tests:** the app must reject or clearly flag each one rather than
  silently importing corrupted cues or crashing (Module 01).
- **Expected result:** a specific, friendly error — not a crash, and not a
  silently-imported broken material.

## Known limitations of this sample set

- No real audio/video codec (e.g. real MP4/H.264) sample is included here —
  packaged-build MP4/H.264 validation is already tracked separately as an
  open release blocker in `PROJECT_STATUS.md` and is out of scope for this
  synthetic set. If you have a real, legally-usable short video clip
  available, you may substitute it for `normal_lesson.wav` in Module 01/13
  to additionally exercise real video decoding — this is optional and not
  required to complete the baseline.
- No legacy (pre-v10 schema) database snapshot is bundled — that upgrade
  path is already covered by Phase C1's packaged-build preflight
  (see `PROJECT_STATUS.md`) and by the project's own migration tests; adding
  a binary database fixture here was judged lower-value than keeping this
  sample set small and text-only.

## Privacy provenance

- All subtitle text and the audio's tone parameters were authored/generated
  specifically for this QA baseline; none of it is copied from any
  copyrighted or real-world source.
- No real names, emails, accounts, customer data, or local absolute paths
  appear in any sample file.
- No secrets, tokens, or credentials appear in any sample file.
- The three `invalid_*` files are copies of this same repository's own
  synthetic test fixtures, already used for automated testing.
