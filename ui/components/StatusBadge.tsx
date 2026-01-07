/**
 * Status badge component showing pass/flagged/reject status.
 */

import type { StatusBadge as StatusBadgeType } from '../types';
import styles from './StatusBadge.module.css';

interface StatusBadgeProps {
  badge: StatusBadgeType;
  reasons?: string[];
}

export function StatusBadge({ badge, reasons = [] }: StatusBadgeProps) {
  return (
    <div className={`${styles.badge} ${styles[badge]}`}>
      <span className={styles.label}>{badge.toUpperCase()}</span>
      {reasons.length > 0 && (
        <ul className={styles.reasons}>
          {reasons.map((reason, idx) => (
            <li key={idx}>{reason}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
