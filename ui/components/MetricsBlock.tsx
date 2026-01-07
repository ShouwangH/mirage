/**
 * Metrics display component showing key metrics from MetricBundleV1.
 * Summary metrics shown at top, with collapsible Video and Face detail sections.
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

export function MetricsBlock({ metrics }: MetricsBlockProps) {
  if (!metrics) {
    return <div className={styles.noMetrics}>No metrics available</div>;
  }

  return (
    <div className={styles.container}>
      {/* Summary metrics - always visible */}
      <dl className={styles.summary}>
        <div className={styles.metric}>
          <dt>Face Present</dt>
          <dd>{formatPercent(metrics.face_present_ratio)}</dd>
        </div>
        <div className={styles.metric}>
          <dt>Mouth-Audio</dt>
          <dd>{formatNumber(metrics.mouth_audio_corr)}</dd>
        </div>
        <div className={styles.metric}>
          <dt>A/V Delta</dt>
          <dd>{metrics.av_duration_delta_ms}ms</dd>
        </div>
        {metrics.lse_d !== null && (
          <div className={styles.metric}>
            <dt>LSE-D</dt>
            <dd>{formatNumber(metrics.lse_d, 1)}</dd>
          </div>
        )}
      </dl>

      {/* Collapsible detail sections */}
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
              <dd>{metrics.av_duration_delta_ms}ms</dd>
            </div>
            <div className={styles.metric}>
              <dt>FPS</dt>
              <dd>{formatNumber(metrics.fps, 1)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Frame Count</dt>
              <dd>{metrics.frame_count}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Scene Cuts</dt>
              <dd>{metrics.scene_cut_count}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Freeze Ratio</dt>
              <dd>{formatPercent(metrics.freeze_frame_ratio)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Flicker Score</dt>
              <dd>{formatNumber(metrics.flicker_score)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Blur Score</dt>
              <dd>{formatNumber(metrics.blur_score, 1)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Frame Diff Spikes</dt>
              <dd>{metrics.frame_diff_spike_count}</dd>
            </div>
            {metrics.lse_d !== null && (
              <div className={styles.metric}>
                <dt>LSE-D (SyncNet)</dt>
                <dd>{formatNumber(metrics.lse_d)}</dd>
              </div>
            )}
            {metrics.lse_c !== null && (
              <div className={styles.metric}>
                <dt>LSE-C (SyncNet)</dt>
                <dd>{formatNumber(metrics.lse_c)}</dd>
              </div>
            )}
          </dl>
        </CollapsibleSection>

        <CollapsibleSection
          title="Face Metrics"
          badge={formatPercent(metrics.face_present_ratio)}
        >
          <dl className={styles.detailGrid}>
            <div className={styles.metric}>
              <dt>Face Present</dt>
              <dd>{formatPercent(metrics.face_present_ratio)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>BBox Jitter</dt>
              <dd>{formatNumber(metrics.face_bbox_jitter, 4)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Landmark Jitter</dt>
              <dd>{formatNumber(metrics.landmark_jitter, 4)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Mouth Energy</dt>
              <dd>{formatNumber(metrics.mouth_open_energy, 4)}</dd>
            </div>
            <div className={styles.metric}>
              <dt>Mouth-Audio Corr</dt>
              <dd>{formatNumber(metrics.mouth_audio_corr)}</dd>
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
            title="Lip Sync (SyncNet)"
            badge={metrics.lse_d !== null ? formatNumber(metrics.lse_d, 1) : '—'}
          >
            <dl className={styles.detailGrid}>
              <div className={styles.metric}>
                <dt>LSE-D (Distance)</dt>
                <dd className={metrics.lse_d !== null && metrics.lse_d < 8 ? styles.good : undefined}>
                  {formatNumber(metrics.lse_d, 2)}
                </dd>
              </div>
              <div className={styles.metric}>
                <dt>LSE-C (Confidence)</dt>
                <dd className={metrics.lse_c !== null && metrics.lse_c > 3 ? styles.good : undefined}>
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
