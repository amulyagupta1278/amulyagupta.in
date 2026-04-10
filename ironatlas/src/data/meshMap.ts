import { MUSCLE_IDS } from './muscles';

/**
 * Maps GLB mesh.name → internal muscle ID.
 *
 * This is the ONLY file you need to edit when your real GLB arrives.
 * Add entries like:
 *   "mixamorig:LeftArm_Bicep": "biceps",
 *   "Body_Pectoralis_Major": "upper_pecs",
 *
 * Leave empty for the placeholder model — placeholder meshes are already
 * named with muscle IDs directly.
 */
export const MESH_NAME_MAP: Record<string, string> = {
  // Real GLB mappings go here. Example:
  // "Bicep_L": "biceps",
  // "Bicep_R": "biceps",
  // "Pec_Major_Upper": "upper_pecs",
};

/**
 * Resolves a GLB mesh name to a muscle ID.
 * First checks the explicit map, then falls back to treating the mesh name
 * as a direct muscle ID (works for placeholder model).
 */
export function getMuscleId(meshName: string): string | null {
  if (meshName in MESH_NAME_MAP) return MESH_NAME_MAP[meshName];
  if (MUSCLE_IDS.has(meshName)) return meshName;
  return null;
}
