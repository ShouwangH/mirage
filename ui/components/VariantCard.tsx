/**
 * Variant card component displaying a single run with video, metrics, and status.
 */

import type { RunDetail } from '../types';
import { getArtifactUrl } from '../lib/api';
import { StatusBadge } from './StatusBadge';
import { VideoPlayer } from './VideoPlayer';
import { MetricsBlock } from './MetricsBlock';
import styles from './VariantCard.module.css';

interface VariantCardProps {
  run: RunDetail;
}

export function VariantCard({ run }: VariantCardProps) {
  const videoUrl = getArtifactUrl(run.output_canon_uri);

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <h3 className={styles.title}>{run.variant_key}</h3>
        {run.status_badge && (
          <StatusBadge badge={run.status_badge} reasons={run.reasons} />
        )}
      </div>

      <div className={styles.status}>
        Status: <span className={styles[run.status]}>{run.status}</span>
      </div>

      {videoUrl ? (
        <VideoPlayer src={videoUrl} />
      ) : (
        <div className={styles.noVideo}>
          {run.status === 'queued' && 'Waiting to process...'}
          {run.status === 'running' && 'Processing...'}
          {run.status === 'failed' && 'Generation failed'}
          {run.status === 'succeeded' && !run.output_canon_uri && 'No video available'}
        </div>
      )}

      <MetricsBlock metrics={run.metrics} />
    </div>
  );
}
