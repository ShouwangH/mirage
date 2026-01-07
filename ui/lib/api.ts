/**
 * API client for Mirage backend.
 */

import type { ExperimentOverview, TaskDetail, HumanSummary } from '../types';

// API base URL - can be overridden via environment variable
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Fetch experiment overview by ID.
 */
export async function getExperiment(id: string): Promise<ExperimentOverview> {
  const res = await fetch(`${API_BASE}/api/experiments/${id}`);
  if (!res.ok) {
    throw new Error(`Experiment not found: ${id}`);
  }
  return res.json();
}

/**
 * Fetch next open task for an experiment.
 */
export async function getNextTask(experimentId: string): Promise<TaskDetail | null> {
  const res = await fetch(`${API_BASE}/api/experiments/${experimentId}/tasks/next`);
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch next task`);
  }
  return res.json();
}

/**
 * Fetch human evaluation summary for an experiment.
 */
export async function getHumanSummary(experimentId: string): Promise<HumanSummary | null> {
  const res = await fetch(`${API_BASE}/api/experiments/${experimentId}/summary`);
  if (res.status === 404) {
    return null;
  }
  if (!res.ok) {
    throw new Error(`Failed to fetch summary`);
  }
  return res.json();
}

/**
 * Create pairwise tasks for an experiment.
 */
export async function createTasks(experimentId: string): Promise<{ tasks_created: number }> {
  const res = await fetch(`${API_BASE}/api/experiments/${experimentId}/tasks`, {
    method: 'POST',
  });
  if (!res.ok) {
    throw new Error(`Failed to create tasks`);
  }
  return res.json();
}

/**
 * Get artifact URL for a given path.
 * Handles both absolute paths and relative paths.
 */
export function getArtifactUrl(path: string | null): string | null {
  if (!path) return null;

  // If path is already a full URL, return as-is
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }

  // Otherwise, construct URL from API base
  // Remove leading slash if present for consistency
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${API_BASE}/artifacts/${cleanPath}`;
}

/**
 * Get the API base URL (for debugging/display).
 */
export function getApiBaseUrl(): string {
  return API_BASE;
}
