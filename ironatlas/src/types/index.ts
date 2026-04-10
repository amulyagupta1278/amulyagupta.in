export interface Exercise {
  name: string;
  primary: string[];
  secondary: string[];
  equipment: string[];
}

export interface MuscleInfo {
  id: string;
  label: string;
  tip: string;
  primaryExercises: Exercise[];
  secondaryExercises: Exercise[];
}

export type CameraPreset = 'front' | 'back' | 'left' | 'right';
