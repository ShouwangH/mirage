/**
 * Collapsible section component with expand/collapse functionality.
 */

import { useState, type ReactNode } from 'react';
import styles from './CollapsibleSection.module.css';

interface CollapsibleSectionProps {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  badge?: string | number;
}

export function CollapsibleSection({
  title,
  children,
  defaultOpen = false,
  badge,
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={styles.container}>
      <button
        className={styles.header}
        onClick={() => setIsOpen(!isOpen)}
        type="button"
        aria-expanded={isOpen}
      >
        <span className={styles.chevron} data-open={isOpen}>
          ▶
        </span>
        <span className={styles.title}>{title}</span>
        {badge !== undefined && (
          <span className={styles.badge}>{badge}</span>
        )}
      </button>
      {isOpen && <div className={styles.content}>{children}</div>}
    </div>
  );
}
