/**
 * Experiment overview page.
 * Displays variant cards with video, metrics, and status badges.
 */

import { GetServerSideProps } from 'next';
import Head from 'next/head';
import { getExperiment } from '../../lib/api';
import { VariantCard } from '../../components/VariantCard';
import type { ExperimentOverview } from '../../types';
import styles from '../../styles/Experiment.module.css';

interface ExperimentPageProps {
  experiment: ExperimentOverview;
}

export default function ExperimentPage({ experiment }: ExperimentPageProps) {
  return (
    <>
      <Head>
        <title>Experiment: {experiment.experiment_id} | Mirage</title>
      </Head>

      <main className={styles.main}>
        <header className={styles.header}>
          <h1>Experiment: {experiment.experiment_id}</h1>
          <span className={`${styles.status} ${styles[experiment.status]}`}>
            {experiment.status}
          </span>
        </header>

        {/* Generation Spec */}
        <section className={styles.section}>
          <h2>Generation Spec</h2>
          <div className={styles.specDetails}>
            <div className={styles.specRow}>
              <span className={styles.label}>Provider:</span>
              <span>{experiment.generation_spec.provider}</span>
            </div>
            <div className={styles.specRow}>
              <span className={styles.label}>Model:</span>
              <span>
                {experiment.generation_spec.model}
                {experiment.generation_spec.model_version &&
                  ` (${experiment.generation_spec.model_version})`}
              </span>
            </div>
            <div className={styles.specRow}>
              <span className={styles.label}>Prompt:</span>
              <span className={styles.prompt}>
                {experiment.generation_spec.prompt_template}
              </span>
            </div>
          </div>
        </section>

        {/* Dataset Item (collapsed) */}
        <details className={styles.section}>
          <summary className={styles.collapsible}>
            <h2>Source Context (optional)</h2>
          </summary>
          <div className={styles.specDetails}>
            <div className={styles.specRow}>
              <span className={styles.label}>Item ID:</span>
              <span>{experiment.dataset_item.item_id}</span>
            </div>
            <div className={styles.specRow}>
              <span className={styles.label}>Subject:</span>
              <span>{experiment.dataset_item.subject_id}</span>
            </div>
          </div>
        </details>

        {/* Variants Grid */}
        <section className={styles.section}>
          <h2>Variants ({experiment.runs.length})</h2>
          <div className={styles.variantsGrid}>
            {experiment.runs.map((run) => (
              <VariantCard key={run.run_id} run={run} />
            ))}
          </div>
        </section>

        {/* Human Evaluation Summary (if available) */}
        {experiment.human_summary && (
          <section className={styles.section}>
            <h2>Human Evaluation Results</h2>
            <div className={styles.results}>
              {experiment.human_summary.recommended_pick && (
                <div className={styles.recommended}>
                  <span className={styles.label}>Recommended Pick:</span>
                  <span className={styles.recommendedValue}>
                    {experiment.runs.find(
                      (r) => r.run_id === experiment.human_summary!.recommended_pick
                    )?.variant_key || experiment.human_summary.recommended_pick}
                  </span>
                </div>
              )}
              <div className={styles.winRates}>
                <h3>Win Rates</h3>
                <ul>
                  {Object.entries(experiment.human_summary.win_rates).map(
                    ([runId, rate]) => {
                      const run = experiment.runs.find((r) => r.run_id === runId);
                      return (
                        <li key={runId}>
                          {run?.variant_key || runId}: {(rate * 100).toFixed(0)}%
                        </li>
                      );
                    }
                  )}
                </ul>
              </div>
              <div className={styles.comparisons}>
                Total comparisons: {experiment.human_summary.total_comparisons}
              </div>
            </div>
          </section>
        )}
      </main>
    </>
  );
}

export const getServerSideProps: GetServerSideProps<ExperimentPageProps> = async ({
  params,
}) => {
  try {
    const experiment = await getExperiment(params?.id as string);
    return { props: { experiment } };
  } catch (error) {
    return { notFound: true };
  }
};
