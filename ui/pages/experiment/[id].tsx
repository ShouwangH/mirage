/**
 * Experiment overview page.
 * Displays variant cards with video, metrics, and status badges.
 */

import { GetServerSideProps } from 'next';
import Head from 'next/head';
import Link from 'next/link';
import { getExperiment, getHumanSummary } from '../../lib/api';
import { VariantCard } from '../../components/VariantCard';
import { Results } from '../../components/Results';
import type { ExperimentOverview, HumanSummary } from '../../types';
import styles from '../../styles/Experiment.module.css';

interface ExperimentPageProps {
  experiment: ExperimentOverview;
  humanSummary: HumanSummary | null;
}

export default function ExperimentPage({ experiment, humanSummary }: ExperimentPageProps) {
  return (
    <>
      <Head>
        <title>Experiment: {experiment.experiment_id} | Mirage</title>
      </Head>

      <main className={styles.main}>
        <header className={styles.header}>
          <div className={styles.headerTitle}>
            <h1>Experiment: {experiment.experiment_id}</h1>
            <span className={`${styles.status} ${styles[experiment.status]}`}>
              {experiment.status}
            </span>
          </div>
          <Link href={`/eval/${experiment.experiment_id}`} className={styles.evalButton}>
            Start Evaluation
          </Link>
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
        {humanSummary && humanSummary.total_comparisons > 0 && (
          <section className={styles.section}>
            <Results
              experimentId={experiment.experiment_id}
              summary={humanSummary}
              runs={experiment.runs}
            />
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
    const id = params?.id as string;
    const experiment = await getExperiment(id);

    // Try to get human summary (may not exist yet)
    let humanSummary: HumanSummary | null = null;
    try {
      humanSummary = await getHumanSummary(id);
    } catch {
      // No summary yet, that's ok
    }

    return { props: { experiment, humanSummary } };
  } catch (error) {
    return { notFound: true };
  }
};
