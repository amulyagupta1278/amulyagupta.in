/**
 * MuscleInfoPanel
 * ───────────────
 * Glassmorphism floating overlay.
 * Desktop: slides in from right.
 * Mobile:  slides up from bottom.
 *
 * Shows muscle name, training tip, and exercise lists
 * for the currently selected muscle.
 */
import { useMemo } from 'react';
import { useAnatomyStore } from '../store/useAnatomyStore';
import { getMuscleInfo } from '../services/muscleService';
import type { Exercise } from '../types';

function ExerciseRow({ ex, variant }: { ex: Exercise; variant: 'primary' | 'secondary' }) {
  return (
    <div className={`exercise-card exercise-card--${variant}`}>
      <span className="exercise-card__name">{ex.name}</span>
      <span className="exercise-card__equip">{ex.equipment[0]}</span>
    </div>
  );
}

export default function MuscleInfoPanel() {
  const selected     = useAnatomyStore(s => s.selectedMuscle);
  const selectMuscle = useAnatomyStore(s => s.selectMuscle);

  const info = useMemo(() => (selected ? getMuscleInfo(selected) : null), [selected]);

  return (
    <aside className={`info-panel${selected ? ' info-panel--open' : ''}`} aria-label="Muscle info">
      {info ? (
        <>
          {/* Header */}
          <div className="info-panel__header">
            <h2 className="info-panel__muscle-name">{info.label}</h2>
            <button
              className="info-panel__close"
              onClick={() => selectMuscle(null)}
              aria-label="Close panel"
            >
              ×
            </button>
          </div>

          {/* Training tip */}
          {info.tip && (
            <p className="info-panel__tip">{info.tip}</p>
          )}

          {/* Primary exercises */}
          {info.primaryExercises.length > 0 && (
            <section>
              <div className="info-panel__section-label">
                Primary Exercises ({info.primaryExercises.length})
              </div>
              {info.primaryExercises.map(ex => (
                <ExerciseRow key={ex.name} ex={ex} variant="primary" />
              ))}
            </section>
          )}

          {/* Secondary exercises */}
          {info.secondaryExercises.length > 0 && (
            <section style={{ marginTop: 14 }}>
              <div className="info-panel__section-label">
                Also Works ({info.secondaryExercises.length})
              </div>
              {info.secondaryExercises.map(ex => (
                <ExerciseRow key={ex.name} ex={ex} variant="secondary" />
              ))}
            </section>
          )}
        </>
      ) : (
        <div className="info-panel__prompt">
          <span className="info-panel__prompt-icon">◎</span>
          <p>Click any muscle group to explore exercises and training tips</p>
        </div>
      )}
    </aside>
  );
}
