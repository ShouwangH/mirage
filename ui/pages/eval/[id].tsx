/**
 * Evaluation page for pairwise video comparison.
 * Route: /eval/[experiment_id]
 */

import { useState, useEffect, useCallback } from 'react';
import { GetServerSideProps } from 'next';
import { useRouter } from 'next/router';
import Head from 'next/head';
import {
  getExperiment,
  getNextTask,
  createTasks,
  getHumanSummary,
} from '../../lib/api';
import type { ExperimentOverview, TaskDetail, RunDetail, HumanSummary } from '../../types';
import { EvalOverlay } from '../../components/EvalOverlay';
import styles from './Eval.module.css';

interface EvalPageProps {
  experiment: ExperimentOverview;
  initialTask: TaskDetail | null;
  initialSummary: HumanSummary | null;
}

export default function EvalPage({
  experiment,
  initialTask,
  initialSummary,
}: EvalPageProps) {
  const router = useRouter();
  const [currentTask, setCurrentTask] = useState<TaskDetail | null>(initialTask);
  const [summary, setSummary] = useState<HumanSummary | null>(initialSummary);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tasksCreated, setTasksCreated] = useState(false);

  // Find runs by ID
  const findRun = useCallback(
    (runId: string): RunDetail | undefined => {
      return experiment.runs.find((r) => r.run_id === runId);
    },
    [experiment.runs]
  );

  // Get left and right runs for current task
  const leftRun = currentTask ? findRun(currentTask.presented_left_run_id) : undefined;
  const rightRun = currentTask ? findRun(currentTask.presented_right_run_id) : undefined;

  // Create tasks if none exist
  const handleCreateTasks = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await createTasks(experiment.experiment_id);
      setTasksCreated(true);
      if (result.tasks_created > 0) {
        // Fetch the first task
        const task = await getNextTask(experiment.experiment_id);
        setCurrentTask(task);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create tasks');
    } finally {
      setLoading(false);
    }
  };

  // Load next task after completing one
  const handleTaskComplete = async () => {
    setLoading(true);
    try {
      const task = await getNextTask(experiment.experiment_id);
      setCurrentTask(task);
      // Refresh summary
      const newSummary = await getHumanSummary(experiment.experiment_id);
      setSummary(newSummary);
    } catch (err) {
      // No more tasks
      setCurrentTask(null);
      // Refresh summary anyway
      try {
        const newSummary = await getHumanSummary(experiment.experiment_id);
        setSummary(newSummary);
      } catch {
        // Ignore summary fetch errors
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    router.push(`/experiment/${experiment.experiment_id}`);
  };

  // Show summary when all tasks are complete
  const allTasksComplete = !currentTask && (tasksCreated || initialTask !== null);

  return (
    <>
      <Head>
        <title>Evaluate: {experiment.experiment_id}</title>
      </Head>

      <main className={styles.main}>
        <header className={styles.header}>
          <h1>Human Evaluation</h1>
          <p className={styles.experimentId}>
            Experiment: {experiment.experiment_id}
          </p>
        </header>

        {error && <div className={styles.error}>{error}</div>}

        {!currentTask && !allTasksComplete && (
          <div className={styles.noTasks}>
            <h2>No evaluation tasks found</h2>
            <p>
              Create pairwise comparison tasks to start evaluating variants.
            </p>
            <button
              onClick={handleCreateTasks}
              disabled={loading}
              className={styles.createButton}
            >
              {loading ? 'Creating...' : 'Create Comparison Tasks'}
            </button>
          </div>
        )}

        {allTasksComplete && (
          <div className={styles.complete}>
            <h2>Evaluation Complete!</h2>
            {summary && (
              <div className={styles.summaryCard}>
                <h3>Results</h3>
                <p>Total comparisons: {summary.total_comparisons}</p>

                <div className={styles.winRates}>
                  <h4>Win Rates</h4>
                  {Object.entries(summary.win_rates).map(([variant, rate]) => (
                    <div key={variant} className={styles.winRate}>
                      <span className={styles.variantName}>{variant}</span>
                      <div className={styles.rateBar}>
                        <div
                          className={styles.rateFill}
                          style={{ width: `${rate * 100}%` }}
                        />
                      </div>
                      <span className={styles.rateValue}>
                        {(rate * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>

                {summary.recommended_pick && (
                  <div className={styles.recommendation}>
                    <strong>Recommended:</strong> {summary.recommended_pick}
                  </div>
                )}
              </div>
            )}
            <button onClick={handleClose} className={styles.backButton}>
              Back to Experiment
            </button>
          </div>
        )}

        {currentTask && leftRun && rightRun && (
          <EvalOverlay
            task={currentTask}
            leftRun={leftRun}
            rightRun={rightRun}
            onComplete={handleTaskComplete}
            onClose={handleClose}
          />
        )}

        {loading && !currentTask && (
          <div className={styles.loading}>Loading...</div>
        )}
      </main>
    </>
  );
}

export const getServerSideProps: GetServerSideProps<EvalPageProps> = async ({
  params,
}) => {
  const id = params?.id as string;

  try {
    const experiment = await getExperiment(id);

    // Try to get next task (may not exist yet)
    let initialTask: TaskDetail | null = null;
    try {
      initialTask = await getNextTask(id);
    } catch {
      // No tasks yet, that's ok
    }

    // Try to get summary
    let initialSummary: HumanSummary | null = null;
    try {
      initialSummary = await getHumanSummary(id);
    } catch {
      // No summary yet
    }

    return {
      props: {
        experiment,
        initialTask,
        initialSummary,
      },
    };
  } catch (error) {
    return {
      notFound: true,
    };
  }
};
