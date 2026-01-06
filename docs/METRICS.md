# METRICS.md — MetricBundleV1 definitions

## principles
- these are sanity/stability proxies; they do not “measure realism”
- metrics must be cheap, deterministic, and versioned
- thresholds (if any) are advisory; use humans for preference

## canonical inputs
all metrics run on:
- `output_canon.mp4` (normalized format)
- extracted audio waveform from canonical audio input

## MetricBundleV1 (required)

### tier 0 (ffmpeg/opencv/numpy)

#### decode_ok
- bool: video can be decoded and has >= 1 frame

#### video_duration_ms / audio_duration_ms
- derived via ffprobe

#### av_duration_delta_ms
- abs(video_duration_ms - audio_duration_ms)

#### fps, frame_count
- fps from ffprobe; frame_count from decoding loop

#### scene_cut_count
- detect abrupt scene changes.
implementation options:
- ffmpeg scene detection (recommended)
- or histogram difference thresholding in opencv

#### freeze_frame_ratio
- ratio of consecutive frames whose pixel difference is below epsilon
- compute:
  - diff_t = mean_abs(frame_t - frame_{t-1})
  - freeze if diff_t < eps
  - ratio = freezes / (frame_count - 1)

#### flicker_score
- captures global luminance instability
- compute per-frame mean luminance (Y) and take:
  - stddev of luminance mean OR mean absolute delta between frames
- higher = more flicker

#### blur_score
- variance of Laplacian on grayscale frames, averaged over time
- lower = blurrier
- record both mean and p10 if useful (optional)

#### frame_diff_spike_count
- count of frames where diff_t is above a high quantile threshold (e.g., > mean + 3*std)
- indicates glitches / sudden jumps

### tier 1 (mediapipe)

#### face_present_ratio
- % frames where face detection returns a face

#### face_bbox_jitter
- average frame-to-frame delta of bbox center + size (normalized by frame size)

#### landmark_jitter
- average frame-to-frame L2 displacement of a fixed subset of landmarks
- normalized by inter-ocular distance (to be scale-invariant)

#### mouth_open_energy
- define mouth openness as distance between upper/lower lip landmarks
- energy = variance over time (or mean absolute delta)
- low energy may indicate “dead mouth”

#### mouth_audio_corr
- compute audio envelope (RMS per frame window)
- compute mouth openness per frame
- compute correlation with small lag search (e.g., +/- 3 frames)
- report max corr

#### blink_count / blink_rate_hz (optional)
- detect blinks via eye aspect ratio (EAR) threshold + debounce

### tier 2 (optional, syncnet)

#### lse_d, lse_c
- SyncNet-derived lip-sync proxy (as implemented by chosen evaluator)
- store null if not computed

## status badges (pass/flag/reject)
badges are derived from metrics + decode sanity:

### reject (hard failure)
- decode_ok = false
- face_present_ratio below a floor (e.g., < 0.2)
- av_duration_delta_ms above a floor (e.g., > 500ms) — adjust per domain

### flagged (review)
- flicker_score high
- freeze_frame_ratio high
- blur_score low
- mouth_audio_corr very low
- (optional) lse_c low / lse_d high

### pass
- not reject and not flagged

**note:** thresholds are demo-tuned. the UI must label these as “review signals.”
