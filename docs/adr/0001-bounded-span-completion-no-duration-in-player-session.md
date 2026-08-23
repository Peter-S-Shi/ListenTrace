# Bounded playback spans complete via logical end or EndOfMedia, never via known media duration

`PlayerSession` stays framework-free and never learns the Material's actual duration. A bounded
playback span (Replay Cue, Play-cue, one Loop iteration) has exactly two legal completion paths:
its logical end is reached during normal position ticks, or the underlying media's physical
EndOfMedia fires first. We rejected computing `min(span.end_ms [+ grace], media_duration)` and
threading duration into `PlayerSession`, because `PlaybackController` already owns and exposes
both `end_of_media` and `duration_ms`/`duration_changed` — duplicating duration-awareness into
the framework-free session would couple it to a Qt/media-backend fact it doesn't need.

`PlayerSession.on_media_ended()` was added to complete this: it shares the same "complete active
span" logic as `on_position_changed()`, so a span that can never reach its logical/effective end
via ticks (because the Material is shorter) still completes deterministically instead of leaving
`_active_span`/`_span_restart_pending` dangling. This closes a pre-existing gap — before this
decision, every window's `_on_end_of_media` only patched local UI state and never notified
`PlayerSession`, and `guided_session_window.py` already carried a comment acknowledging the
resulting stuck state for Comparison Replay. Scope was deliberately widened from Loop End Grace
alone to all bounded span types, since the underlying `_ActiveSpan` model doesn't distinguish
loop from non-loop and a split fix would reintroduce two inconsistent completion paths.
