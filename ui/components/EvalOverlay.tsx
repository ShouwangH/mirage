/**
 * EvalOverlay component for pairwise video comparison.
 * Shows two videos side-by-side and allows rating on multiple criteria.
 */

import { useState, useRef, useEffect } from 'react';
import type { TaskDetail, RunDetail, Choice } from '../types';
import { getArtifactUrl, submitRating } from '../lib/api';
import styles from './EvalOverlay.module.css';

interface EvalOverlayProps {
  task: TaskDetail;
  leftRun: RunDetail;
  rightRun: RunDetail;
  onComplete: () => void;
  onClose: () => void;
}

export function EvalOverlay({
  task,
  leftRun,
  rightRun,
  onComplete,
  onClose,
}: EvalOverlayProps) {
  const [choiceRealism, setChoiceRealism] = useState<Choice | null>(null);
  const [choiceLipsync, setChoiceLipsync] = useState<Choice | null>(null);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const leftVideoRef = useRef<HTMLVideoElement>(null);
  const rightVideoRef = useRef<HTMLVideoElement>(null);

  // Sync video playback
  const handlePlay = () => {
    leftVideoRef.current?.play();
    rightVideoRef.current?.play();
  };

  const handlePause = () => {
    leftVideoRef.current?.pause();
    rightVideoRef.current?.pause();
  };

  const handleRestart = () => {
    if (leftVideoRef.current) {
      leftVideoRef.current.currentTime = 0;
    }
    if (rightVideoRef.current) {
      rightVideoRef.current.currentTime = 0;
    }
    handlePlay();
  };

  // Get video URLs
  const leftVideoUrl = getArtifactUrl(leftRun.output_canon_uri);
  const rightVideoUrl = getArtifactUrl(rightRun.output_canon_uri);

  const canSubmit = choiceRealism !== null && choiceLipsync !== null;

  const handleSubmit = async () => {
    if (!canSubmit) return;

    setSubmitting(true);
    setError(null);

    try {
      // Generate a simple rater ID (in production, this would come from auth)
      const raterId = `anon_${Date.now()}`;

      await submitRating({
        task_id: task.task_id,
        rater_id: raterId,
        choice_realism: choiceRealism!,
        choice_lipsync: choiceLipsync!,
        notes: notes || null,
      });

      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit rating');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.container}>
        <div className={styles.header}>
          <h2>Pairwise Comparison</h2>
          <button className={styles.closeButton} onClick={onClose}>
            &times;
          </button>
        </div>

        <div className={styles.videoSection}>
          <div className={styles.videoContainer}>
            <h3 className={styles.videoLabel}>Video A</h3>
            {leftVideoUrl ? (
              <video
                ref={leftVideoRef}
                src={leftVideoUrl}
                className={styles.video}
                controls
                preload="metadata"
              />
            ) : (
              <div className={styles.noVideo}>No video available</div>
            )}
          </div>

          <div className={styles.videoContainer}>
            <h3 className={styles.videoLabel}>Video B</h3>
            {rightVideoUrl ? (
              <video
                ref={rightVideoRef}
                src={rightVideoUrl}
                className={styles.video}
                controls
                preload="metadata"
              />
            ) : (
              <div className={styles.noVideo}>No video available</div>
            )}
          </div>
        </div>

        <div className={styles.controls}>
          <button onClick={handlePlay} className={styles.controlButton}>
            Play Both
          </button>
          <button onClick={handlePause} className={styles.controlButton}>
            Pause Both
          </button>
          <button onClick={handleRestart} className={styles.controlButton}>
            Restart
          </button>
        </div>

        <div className={styles.ratingSection}>
          <div className={styles.criterion}>
            <h4>Realism</h4>
            <p className={styles.criterionDesc}>
              Which video looks more realistic overall?
            </p>
            <div className={styles.choices}>
              <ChoiceButton
                label="A"
                selected={choiceRealism === 'left'}
                onClick={() => setChoiceRealism('left')}
              />
              <ChoiceButton
                label="Tie"
                selected={choiceRealism === 'tie'}
                onClick={() => setChoiceRealism('tie')}
              />
              <ChoiceButton
                label="B"
                selected={choiceRealism === 'right'}
                onClick={() => setChoiceRealism('right')}
              />
              <ChoiceButton
                label="Skip"
                selected={choiceRealism === 'skip'}
                onClick={() => setChoiceRealism('skip')}
                secondary
              />
            </div>
          </div>

          <div className={styles.criterion}>
            <h4>Lip Sync</h4>
            <p className={styles.criterionDesc}>
              Which video has better lip synchronization with audio?
            </p>
            <div className={styles.choices}>
              <ChoiceButton
                label="A"
                selected={choiceLipsync === 'left'}
                onClick={() => setChoiceLipsync('left')}
              />
              <ChoiceButton
                label="Tie"
                selected={choiceLipsync === 'tie'}
                onClick={() => setChoiceLipsync('tie')}
              />
              <ChoiceButton
                label="B"
                selected={choiceLipsync === 'right'}
                onClick={() => setChoiceLipsync('right')}
              />
              <ChoiceButton
                label="Skip"
                selected={choiceLipsync === 'skip'}
                onClick={() => setChoiceLipsync('skip')}
                secondary
              />
            </div>
          </div>

          <div className={styles.notesSection}>
            <label htmlFor="notes">Notes (optional)</label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Any observations about the videos..."
              className={styles.notesInput}
            />
          </div>
        </div>

        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.actions}>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            className={styles.submitButton}
          >
            {submitting ? 'Submitting...' : 'Submit Rating'}
          </button>
        </div>
      </div>
    </div>
  );
}

interface ChoiceButtonProps {
  label: string;
  selected: boolean;
  onClick: () => void;
  secondary?: boolean;
}

function ChoiceButton({ label, selected, onClick, secondary }: ChoiceButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`${styles.choiceButton} ${selected ? styles.selected : ''} ${
        secondary ? styles.secondary : ''
      }`}
    >
      {label}
    </button>
  );
}
