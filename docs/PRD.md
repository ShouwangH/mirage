# PRD.md — a-roll eval loop (mvp)

## 1) goal

build a small internal-style tool that:
- generates 3–5 talking-head variants from the same canonical audio + target constraints
- computes a cheap, mostly-free metric suite (sanity + stability + face/mouth signals)
- optionally computes one “serious” lip-sync proxy (syncnet lse-d/lse-c) if install succeeds
- runs a pairwise human preference loop (30–60 seconds) and outputs:
  - recommended pick for export
  - win-rate rankings
  - flagged/reject reasons with suggested next actions (advisory only)

the point is not “solve realism.” it’s: make subjective quality *iterable*, reproducible, and debuggable.

## 2) target user

mirage internal users:
- product engineers deciding which variant to ship
- applied ai engineers/researchers debugging regressions and slice failures

## 3) scope (hard)

### in-scope (mvp)
- fixed demo dataset (1–2 clips, self-owned)
- 1 provider/model integration (configurable, but only one required)
- seed sweep (3–5 variants)
- artifact normalization to a canonical mp4 format (browser-safe)
- metric suite:
  - tier 0 (ffmpeg/opencv/numpy): decode sanity, a/v duration delta, freeze detection, flicker score, blur score, scene-cut detection
  - tier 1 (mediapipe): face present %, bbox jitter, landmark jitter, mouth openness energy, mouth↔audio envelope correlation, blink events (optional)
  - tier 2 (stretch): syncnet lse-d/lse-c
- human eval overlay:
  - pairwise comparisons
  - questions: realism overall, lip-sync, (optional) matches target constraints
  - randomize left/right and record the flip
- results:
  - win-rate by variant
  - show metric values alongside votes (no “realism score”)
  - reject/flag reasons + suggested next actions
- export: download the recommended clip

### out-of-scope (explicit non-goals)
- public uploads / multi-user auth
- voice cloning
- automatic prompt rewriting / “agentic” edits
- multi-provider routing/fallback
- distributed orchestration (temporal, queues, etc.)
- scaling beyond local single-machine runs
- “ground truth” reconstruction metrics against the source video

## 4) demo script (frozen)

this is the actual flow you must be able to demo in <2 minutes:

1) open `/experiment/demo`
2) see source context (collapsed) and canonical audio + target constraints
3) see 3–5 generated variants with metrics + pass/flag/reject badges
4) click **evaluate variants**
5) complete 3 pairwise tasks (A vs B, B vs C, A vs C)
6) return to overview and show:
   - recommended pick
   - win rates
   - one flagged/reject reason and the suggested next action
7) click export for the recommended pick

## 5) product UX requirements

### overview page
- show source clip collapsed (“optional context”)
- show canonical audio (fixed input)
- show target constraints string (immutable within a run)
- show variant cards with:
  - play
  - view spec (prompt+params+input hashes)
  - metric block
  - status badge + reason

### evaluate overlay
- side-by-side playback, sync-start
- questions:
  - which looks more realistic overall?
  - which has better lip-sync?
  - (optional) which better matches target constraints?
- buttons:
  - submit & next
  - skip (unclear)

### review queue
- list rejects + flagged with:
  - reason
  - impact hint
  - suggested next action (advisory)
  - buttons:
    - re-run (same spec) [idempotent]
    - create new variant… [explicit diff, new label]

## 6) safety + framing requirements

- demo uses self-owned footage only
- UI copy avoids “deepfake builder” framing:
  - no “remove beard” headline features
  - constraints shown as generic “target constraints”
- source clip not emphasized; canonical audio is the fixed driver

## 7) success criteria (definition of done)

must-haves:
- one-command seed + run produces stable artifacts (or uses cached outputs)
- re-running does not duplicate runs or overwrite artifacts (idempotent)
- outputs play correctly in browser (canonical transcode)
- pairwise eval updates win-rates and recommended pick
- flagged/reject reasons visible and plausible
- syncnet is optional; mvp still ships without it

stretch:
- syncnet lse-d/lse-c computed for each variant

## 8) risks + mitigations

- syncnet install yak shave → timebox to 4 hours; if not done, ship without syncnet
- provider instability → ship with cached generated outputs + still compute metrics + run human eval
- demo looks toy-ish → enforce canonical transcode, clean UI copy, and “workflow” (review queue + recommended pick)
- “agent overrides intent” failure mode → specs immutable; any change = new variant with explicit diff
