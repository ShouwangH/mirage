/**
 * Metrics display component showing key metrics from MetricBundleV1.
 */

import type { MetricBundleV1 } from '../types';
import styles from './MetricsBlock.module.css';

interface MetricsBlockProps {
  metrics: MetricBundleV1 | null;
}

export function MetricsBlock({ metrics }: MetricsBlockProps) {
  if (!metrics) {
    return <div className={styles.noMetrics}>No metrics available</div>;
  }

  return (
    <div className={styles.container}>
      <dl className={styles.metrics}>
        {/* Key quality metrics */}
        <div className={styles.metric}>
          <dt>Face Present</dt>
          <dd>{(metrics.face_present_ratio * 100).toFixed(0)}%</dd>
        </div>

        <div className={styles.metric}>
          <dt>Mouth-Audio Corr</dt>
          <dd>{metrics.mouth_audio_corr.toFixed(2)}</dd>
        </div>

        <div className={styles.metric}>
          <dt>A/V Delta</dt>
          <dd>{metrics.av_duration_delta_ms}ms</dd>
        </div>

        <div className={styles.metric}>
          <dt>Freeze Ratio</dt>
          <dd>{(metrics.freeze_frame_ratio * 100).toFixed(1)}%</dd>
        </div>

        <div className={styles.metric}>
          <dt>Blur Score</dt>
          <dd>{metrics.blur_score.toFixed(1)}</dd>
        </div>

        <div className={styles.metric}>
          <dt>Flicker</dt>
          <dd>{metrics.flicker_score.toFixed(2)}</dd>
        </div>

        {/* Optional SyncNet metrics */}
        {metrics.lse_d !== null && (
          <div className={styles.metric}>
            <dt>LSE-D</dt>
            <dd>{metrics.lse_d.toFixed(2)}</dd>
          </div>
        )}

        {metrics.lse_c !== null && (
          <div className={styles.metric}>
            <dt>LSE-C</dt>
            <dd>{metrics.lse_c.toFixed(2)}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
