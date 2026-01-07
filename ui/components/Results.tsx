/**
 * Results component for displaying experiment evaluation results.
 * Shows win rates, recommended pick, and export button.
 */

import type { HumanSummary, RunDetail } from '../types';
import { getApiBaseUrl } from '../lib/api';
import styles from './Results.module.css';

interface ResultsProps {
  experimentId: string;
  summary: HumanSummary;
  runs: RunDetail[];
}

export function Results({ experimentId, summary, runs }: ResultsProps) {
  const apiBase = getApiBaseUrl();

  // Map run IDs to variant keys for display
  const getVariantKey = (runId: string): string => {
    const run = runs.find((r) => r.run_id === runId);
    return run?.variant_key || runId.slice(0, 8);
  };

  // Sort win rates by percentage (descending)
  const sortedWinRates = Object.entries(summary.win_rates).sort(
    ([, a], [, b]) => b - a
  );

  const handleExport = () => {
    // Open export URL in new tab (triggers download)
    window.open(`${apiBase}/api/experiments/${experimentId}/export`, '_blank');
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h2>Evaluation Results</h2>
        <button onClick={handleExport} className={styles.exportButton}>
          Export Results
        </button>
      </div>

      {summary.recommended_pick && (
        <div className={styles.recommendation}>
          <span className={styles.recommendLabel}>Recommended Pick:</span>
          <span className={styles.recommendValue}>
            {getVariantKey(summary.recommended_pick)}
          </span>
        </div>
      )}

      <div className={styles.stats}>
        <span>Total comparisons: {summary.total_comparisons}</span>
      </div>

      <div className={styles.winRates}>
        <h3>Win Rates</h3>
        {sortedWinRates.map(([runId, rate]) => {
          const variantKey = getVariantKey(runId);
          const percentage = (rate * 100).toFixed(1);
          const isRecommended = runId === summary.recommended_pick;

          return (
            <div
              key={runId}
              className={`${styles.winRateRow} ${
                isRecommended ? styles.recommended : ''
              }`}
            >
              <span className={styles.variantName}>
                {variantKey}
                {isRecommended && <span className={styles.star}> ★</span>}
              </span>
              <div className={styles.barContainer}>
                <div
                  className={styles.bar}
                  style={{ width: `${Math.max(rate * 100, 2)}%` }}
                />
              </div>
              <span className={styles.percentage}>{percentage}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
