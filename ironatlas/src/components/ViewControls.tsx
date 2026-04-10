/**
 * ViewControls
 * ────────────
 * Camera preset buttons — fixed bottom-center pill.
 * Triggers smooth camera animation via the Zustand store → CameraRig.
 */
import { useAnatomyStore } from '../store/useAnatomyStore';
import type { CameraPreset } from '../types';

const PRESETS: { id: CameraPreset; label: string }[] = [
  { id: 'front', label: 'Front' },
  { id: 'back',  label: 'Back'  },
  { id: 'left',  label: 'Left'  },
  { id: 'right', label: 'Right' },
];

export default function ViewControls() {
  const active = useAnatomyStore(s => s.cameraPreset);
  const set    = useAnatomyStore(s => s.setCameraPreset);

  return (
    <nav className="view-controls" aria-label="Camera presets">
      {PRESETS.map(({ id, label }) => (
        <button
          key={id}
          className={`view-btn${active === id ? ' view-btn--active' : ''}`}
          onClick={() => set(id)}
          aria-pressed={active === id}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
