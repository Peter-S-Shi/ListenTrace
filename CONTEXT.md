# ListenTrace

A local-first desktop app for learning a language by listening to subtitled audio/video material and practicing against individual subtitle cues.

## Language

**Material**:
A single imported audio/video file with its subtitle track, identified by `material.id`.
_Avoid_: File, media, source.

**Cue**:
One subtitle-defined interval within a Material's transcript, with its own start/end timestamp.
_Avoid_: Line, subtitle entry, segment.

**Replay Cue**:
Play exactly one Cue once, then pause. A one-shot bounded playback span with no restart.
_Avoid_: Repeat, single play.

**Loop Cue** / **Loop Range**:
Repeat playback of a single Cue, or of a contiguous run of Cues, indefinitely until stopped. Loop Range is one indivisible span from the first selected Cue's start to the last selected Cue's end; Cues in between have no boundary of their own inside the loop.
_Avoid_: Repeat mode, A-B loop.

**Bounded playback span**:
Any one-shot interval of continuous playback with a defined start and a defined logical end — the shared underlying primitive behind Replay Cue, Play-cue, one iteration of Loop Cue, and one iteration of Loop Range. Ends either by reaching its logical end during normal playback, or by the Material's physical end (EndOfMedia) arriving first.
_Avoid_: Segment, region.

**Logical end**:
The subtitle-defined end timestamp of a bounded playback span (a Cue's or a range's end), independent of where the underlying Material's audio actually stops.
_Avoid_: Boundary, endpoint (ambiguous with effective completion end).

**Loop End Grace**:
A configurable extra duration (`loop_end_grace_ms`, product range 60–300ms, default 200ms — raised from an initial 180ms after human calibration across three materially different samples all required 200ms for a complete tail) that a Loop-mode bounded playback span is allowed to keep playing past its logical end before that iteration completes and the loop restarts. Lets the Material's own tail audio finish naturally instead of being cut at the subtitle-defined boundary. Applies only to Loop iterations, never to Replay Cue or Play-cue. May be overridden per Material; a Material with no override inherits the global default.
_Avoid_: Pause, settle delay, restart delay — those describe unrelated backend playback-transition timing, not this concept.

**Effective completion end**:
The actual timestamp at which a given bounded playback span iteration completes: the Logical End for Replay Cue/Play-cue, or Logical End + Loop End Grace for a Loop iteration.
_Avoid_: End, boundary (both ambiguous with Logical End).
