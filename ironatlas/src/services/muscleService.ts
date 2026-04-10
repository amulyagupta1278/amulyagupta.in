import { EXERCISES } from '../data/exercises';
import { GROUP_LABELS, MUSCLE_TO_IDS, TIPS } from '../data/muscles';
import type { MuscleInfo } from '../types';

/**
 * Returns full muscle info for a given muscle ID.
 * Swap internals here (not in components) when moving to an API.
 */
export function getMuscleInfo(muscleId: string): MuscleInfo | null {
  const label = GROUP_LABELS[muscleId];
  if (!label) return null;

  return {
    id: muscleId,
    label,
    tip: TIPS[muscleId] ?? '',
    primaryExercises: EXERCISES.filter(ex =>
      ex.primary.some(m => MUSCLE_TO_IDS[m]?.includes(muscleId))
    ),
    secondaryExercises: EXERCISES.filter(ex =>
      ex.secondary.some(m => MUSCLE_TO_IDS[m]?.includes(muscleId))
    ),
  };
}
