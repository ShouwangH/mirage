/**
 * Metrics display component showing key metrics from MetricBundleV1.
 * Collapsible Video, Face, and Lip Sync detail sections.
 * Good values are highlighted in green.
 */

import type { MetricBundleV1 } from '../types';
import { CollapsibleSection } from './CollapsibleSection';
import styles from './MetricsBlock.module.css';

interface MetricsBlockProps {
  metrics: MetricBundleV1 | null;
}

function formatDuration(ms: number): string {
  const seconds = ms / 1000;
  return `${seconds.toFixed(2)}s`;
}

function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(0)}%`;
}

function formatNumber(value: number | null, decimals = 2): string {
  if (value === null) return '—';
  return value.toFixed(decimals);
}

// Threshold checks for good values
const isGoodAvDelta = (ms: number) => ms < 100;
const isGoodFps = (fps: number) => fps >= 24 && fps <= 30;
const isGoodFreeze = (ratio: number) => ratio < 0.1;
const isGoodFlicker = (score: number) => score < 5;
const isGoodBlur = (score: number) => score > 100;
const isGoodSceneCuts = (count: number) => count === 0;
const isGoodSpikes = (count: number) => count <= 2;
const isGoodFacePresent = (ratio: number) => ratio > 0.9;
const isGoodBboxJitter = (jitter: number) => jitter < 0.01;
const isGoodLandmarkJitter = (jitter: number) => jitter < 0.02;
const isGoodMouthEnergy = (energy: number) => energy > 0.001;
const isGoodMouthCorr = (corr: number) => corr > 0.3;
const isGoodLseD = (lse: number | null) => lse !== null && lse < 8;
const isGoodLseC = (lse: number | null) => lse !== null && lse > 3;

export function MetricsBlock({ metrics }: MetricsBlockProps) {
  if (!metrics) {
    return <div className={styles.noMetrics}>No metrics available</div>;
  }

  return (
    <div className={styles.container}>
      <div className={styles.details}>
        <CollapsibleSection
          title="Video Metrics"
          badge={metrics.decode_ok ? 'OK' : 'ERR'}
        >
          <dl className={styles.detailGrid}>
            <div className={styles.metric}>
              <dt>Video Duration</dt>
              <dd>{formatDuration(metrics.video_duration_ms)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Audio Duration</dt>
              <dd>{formatDuration(metrics.audio_duration_ms)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>A/V Delta</dt>
              <dd className={isGoodAvDelta(metrics.av_duration_delta_ms) ? styles.good : undefined}>
                {metrics.av_duration_delta_ms}ms
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>FPS</dt>
              <dd className={isGoodFps(metrics.fps) ? styles.good : undefined}>
                {formatNumber(metrics.fps, 1)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Frame Count</dt>
              <dd>{metrics.frame_count}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Scene Cuts</dt>
              <dd className={isGoodSceneCuts(metrics.scene_cut_count) ? styles.good : undefined}>
                {metrics.scene_cut_count}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Freeze Ratio</dt>
              <dd className={isGoodFreeze(metrics.freeze_frame_ratio) ? styles.good : undefined}>
                {formatPercent(metrics.freeze_frame_ratio)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Flicker Score</dt>
              <dd className={isGoodFlicker(metrics.flicker_score) ? styles.good : undefined}>
                {formatNumber(metrics.flicker_score)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Blur Score</dt>
              <dd className={isGoodBlur(metrics.blur_score) ? styles.good : undefined}>
                {formatNumber(metrics.blur_score, 1)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Frame Diff Spikes</dt>
              <dd className={isGoodSpikes(metrics.frame_diff_spike_count) ? styles.good : undefined}>
                {metrics.frame_diff_spike_count}
              </dd>
            </div>
          </dl>
        </CollapsibleSection>

        <CollapsibleSection
          title="Face Metrics"
          badge={formatPercent(metrics.face_present_ratio)}
        >
          <dl className={styles.detailGrid}>
            <div className={styles.metric}>
              <dt>Face Present</dt>
              <dd className={isGoodFacePresent(metrics.face_present_ratio) ? styles.good : undefined}>
                {formatPercent(metrics.face_present_ratio)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>BBox Jitter</dt>
              <dd className={isGoodBboxJitter(metrics.face_bbox_jitter) ? styles.good : undefined}>
                {formatNumber(metrics.face_bbox_jitter, 4)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Landmark Jitter</dt>
              <dd className={isGoodLandmarkJitter(metrics.landmark_jitter) ? styles.good : undefined}>
                {formatNumber(metrics.landmark_jitter, 4)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Mouth Energy</dt>
              <dd className={isGoodMouthEnergy(metrics.mouth_open_energy) ? styles.good : undefined}>
                {formatNumber(metrics.mouth_open_energy, 4)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Mouth-Audio Corr</dt>
              <dd className={isGoodMouthCorr(metrics.mouth_audio_corr) ? styles.good : undefined}>
                {formatNumber(metrics.mouth_audio_corr)}
              </dd>
            </div>
            <div className={styles.metric}>
              <dt>Blink Count</dt>
              <dd>{metrics.blink_count ?? '—'}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Blink Rate</dt>
              <dd>
                {metrics.blink_rate_hz !== null
                  ? `${formatNumber(metrics.blink_rate_hz)} Hz`
                  : '—'}
              </dd>
            </div>
          </dl>
        </CollapsibleSection>

        {(metrics.lse_d !== null || metrics.lse_c !== null) && (
          <CollapsibleSection
            title="Lip Sync"
            badge={metrics.lse_d !== null ? formatNumber(metrics.lse_d, 1) : '—'}
          >
            <dl className={styles.detailGrid}>
              <div className={styles.metric}>
                <dt>LSE-D (Distance)</dt>
                <dd className={isGoodLseD(metrics.lse_d) ? styles.good : undefined}>
                  {formatNumber(metrics.lse_d, 2)}
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>LSE-C (Confidence)</dt>
                <dd className={isGoodLseC(metrics.lse_c) ? styles.good : undefined}>
                  {formatNumber(metrics.lse_c, 2)}
                </dd>
              </div>
            </dl>
            <p className={styles.hint}>
              LSE-D: lower is better ({"<"}8 good). LSE-C: higher is better ({">"}3 good).
            </p>
          </CollapsibleSection>
        )}
      </div>
    </div>
  );
}
