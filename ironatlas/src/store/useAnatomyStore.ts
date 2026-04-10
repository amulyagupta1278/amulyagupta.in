import { create } from 'zustand';
import type { CameraPreset } from '../types';

interface AnatomyState {
  selectedMuscle: string | null;
  hoveredMuscle: string | null;
  cameraPreset: CameraPreset;

  selectMuscle: (id: string | null) => void;
  hoverMuscle: (id: string | null) => void;
  setCameraPreset: (preset: CameraPreset) => void;
}

export const useAnatomyStore = create<AnatomyState>((set) => ({
  selectedMuscle: null,
  hoveredMuscle: null,
  cameraPreset: 'front',

  selectMuscle: (id) => set({ selectedMuscle: id }),
  hoverMuscle: (id) => set({ hoveredMuscle: id }),
  setCameraPreset: (preset) => set({ cameraPreset: preset }),
}));
