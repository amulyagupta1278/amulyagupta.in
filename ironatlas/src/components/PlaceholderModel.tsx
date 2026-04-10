/**
 * PlaceholderModel
 * ────────────────
 * A humanoid built from Three.js primitives, each mesh named with a
 * muscle ID. Fully interactive — click, hover, highlight — identical
 * behaviour to the real GLB model.
 *
 * Replace this with AnatomyModel's GLBModel once your .glb is ready.
 */
import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import type { ThreeEvent } from '@react-three/fiber';
import { useAnatomyStore } from '../store/useAnatomyStore';

// ── Colours ───────────────────────────────────────────────
const C_MUSCLE  = '#2e2a3d'; // default muscle mesh colour
const C_BODY    = '#19172099'; // non-interactive skeleton
const C_SELECT  = '#c4864e'; // emissive when selected
const C_HOVER   = '#5a3010'; // emissive when hovered

// ── Muscle mesh definitions ───────────────────────────────
// Each entry becomes one clickable Three.js Box mesh.
// Multiple entries share the same `id` for bilateral muscles (L+R).
type MeshDef = { id: string; pos: [number,number,number]; s: [number,number,number] };

const MUSCLE_MESHES: MeshDef[] = [
  // Neck
  { id: 'neck',         pos: [ 0,    1.52,  0    ], s: [0.15, 0.18, 0.15] },

  // Chest (front surface overlays)
  { id: 'upper_pecs',   pos: [ 0,    1.10,  0.13 ], s: [0.50, 0.18, 0.06] },
  { id: 'middle_pecs',  pos: [ 0,    0.93,  0.13 ], s: [0.45, 0.16, 0.06] },
  { id: 'lower_pecs',   pos: [ 0,    0.78,  0.12 ], s: [0.42, 0.14, 0.06] },

  // Abs (front)
  { id: 'upper_abs',    pos: [ 0,    0.62,  0.12 ], s: [0.30, 0.18, 0.06] },
  { id: 'lower_abs',    pos: [ 0,    0.44,  0.12 ], s: [0.28, 0.16, 0.06] },

  // Obliques (bilateral — same id → same material → shared highlight)
  { id: 'obliques',     pos: [-0.28, 0.55,  0.08 ], s: [0.12, 0.28, 0.06] },
  { id: 'obliques',     pos: [ 0.28, 0.55,  0.08 ], s: [0.12, 0.28, 0.06] },

  // Back (rear surface)
  { id: 'upper_traps',  pos: [ 0,    1.26, -0.13 ], s: [0.56, 0.18, 0.06] },
  { id: 'upper_back',   pos: [ 0,    1.01, -0.13 ], s: [0.50, 0.28, 0.06] },
  { id: 'lower_back',   pos: [ 0,    0.72, -0.13 ], s: [0.40, 0.20, 0.06] },

  // Shoulders
  { id: 'front_delts',  pos: [-0.44, 1.28,  0.10 ], s: [0.14, 0.14, 0.10] },
  { id: 'front_delts',  pos: [ 0.44, 1.28,  0.10 ], s: [0.14, 0.14, 0.10] },
  { id: 'side_delts',   pos: [-0.53, 1.25,  0    ], s: [0.10, 0.20, 0.14] },
  { id: 'side_delts',   pos: [ 0.53, 1.25,  0    ], s: [0.10, 0.20, 0.14] },
  { id: 'rear_delts',   pos: [-0.44, 1.28, -0.10 ], s: [0.14, 0.14, 0.10] },
  { id: 'rear_delts',   pos: [ 0.44, 1.28, -0.10 ], s: [0.14, 0.14, 0.10] },

  // Upper arms
  { id: 'biceps',       pos: [-0.54, 0.86,  0.06 ], s: [0.10, 0.30, 0.10] },
  { id: 'biceps',       pos: [ 0.54, 0.86,  0.06 ], s: [0.10, 0.30, 0.10] },
  { id: 'triceps',      pos: [-0.54, 0.86, -0.06 ], s: [0.10, 0.30, 0.10] },
  { id: 'triceps',      pos: [ 0.54, 0.86, -0.06 ], s: [0.10, 0.30, 0.10] },

  // Forearms
  { id: 'forearms',     pos: [-0.54, 0.50,  0    ], s: [0.09, 0.27, 0.09] },
  { id: 'forearms',     pos: [ 0.54, 0.50,  0    ], s: [0.09, 0.27, 0.09] },

  // Glutes (back)
  { id: 'glutes',       pos: [-0.14, 0.10, -0.14 ], s: [0.20, 0.20, 0.08] },
  { id: 'glutes',       pos: [ 0.14, 0.10, -0.14 ], s: [0.20, 0.20, 0.08] },

  // Hips
  { id: 'hip_abductor', pos: [-0.34, 0.04,  0    ], s: [0.10, 0.17, 0.12] },
  { id: 'hip_abductor', pos: [ 0.34, 0.04,  0    ], s: [0.10, 0.17, 0.12] },
  { id: 'hip_adductor', pos: [-0.14,-0.06,  0.04 ], s: [0.10, 0.17, 0.10] },
  { id: 'hip_adductor', pos: [ 0.14,-0.06,  0.04 ], s: [0.10, 0.17, 0.10] },

  // Thighs
  { id: 'quads',        pos: [-0.18,-0.48,  0.09 ], s: [0.16, 0.44, 0.10] },
  { id: 'quads',        pos: [ 0.18,-0.48,  0.09 ], s: [0.16, 0.44, 0.10] },
  { id: 'hamstrings',   pos: [-0.18,-0.48, -0.09 ], s: [0.16, 0.44, 0.10] },
  { id: 'hamstrings',   pos: [ 0.18,-0.48, -0.09 ], s: [0.16, 0.44, 0.10] },

  // Calves
  { id: 'calves',       pos: [-0.16,-1.00,  0    ], s: [0.12, 0.36, 0.13] },
  { id: 'calves',       pos: [ 0.16,-1.00,  0    ], s: [0.12, 0.36, 0.13] },
];

export default function PlaceholderModel() {
  const selected   = useAnatomyStore(s => s.selectedMuscle);
  const hovered    = useAnatomyStore(s => s.hoveredMuscle);
  const selectMuscle = useAnatomyStore(s => s.selectMuscle);
  const hoverMuscle  = useAnatomyStore(s => s.hoverMuscle);

  // ── One shared material per muscle ID (very efficient) ──
  const materials = useMemo(() => {
    const map: Record<string, THREE.MeshStandardMaterial> = {};
    const seen = new Set<string>();
    for (const { id } of MUSCLE_MESHES) {
      if (seen.has(id)) continue;
      seen.add(id);
      map[id] = new THREE.MeshStandardMaterial({
        color:      new THREE.Color(C_MUSCLE),
        roughness:  0.72,
        metalness:  0.08,
        transparent: true,
        opacity:     1,
      });
    }
    return map;
  }, []);

  // ── Sync materials with store state ─────────────────────
  useEffect(() => {
    for (const [id, mat] of Object.entries(materials)) {
      const isSel = selected === id;
      const isHov = hovered  === id;
      mat.emissive.set(isSel ? C_SELECT : isHov ? C_HOVER : '#000000');
      mat.emissiveIntensity = isSel ? 0.90 : isHov ? 0.45 : 0;
      mat.opacity = selected && !isSel ? 0.18 : 1.0;
    }
  }, [selected, hovered, materials]);

  // ── Cleanup materials on unmount ─────────────────────────
  useEffect(() => () => { Object.values(materials).forEach(m => m.dispose()); }, [materials]);

  // ── Event handlers ───────────────────────────────────────
  const onClick  = (id: string) => (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    selectMuscle(selected === id ? null : id);
  };
  const onOver   = (id: string) => (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    hoverMuscle(id);
    document.body.style.cursor = 'pointer';
  };
  const onOut    = () => { hoverMuscle(null); document.body.style.cursor = 'default'; };

  const bodyMat = useMemo(() => new THREE.MeshStandardMaterial({
    color: new THREE.Color(C_BODY), roughness: 0.9, transparent: true, opacity: 0.6,
  }), []);

  return (
    <group>
      {/* ── Non-interactive skeleton ───────────────────── */}
      {/* Head */}
      <mesh position={[0, 1.72, 0]} material={bodyMat}>
        <sphereGeometry args={[0.14, 16, 16]} />
      </mesh>
      {/* Torso core */}
      <mesh position={[0, 0.78, 0]} material={bodyMat}>
        <boxGeometry args={[0.50, 1.00, 0.28]} />
      </mesh>
      {/* Shoulder width connector */}
      <mesh position={[0, 1.28, 0]} material={bodyMat}>
        <boxGeometry args={[0.90, 0.18, 0.26]} />
      </mesh>
      {/* Upper arms base */}
      <mesh position={[-0.54, 0.86, 0]} material={bodyMat}>
        <boxGeometry args={[0.12, 0.35, 0.13]} />
      </mesh>
      <mesh position={[0.54, 0.86, 0]} material={bodyMat}>
        <boxGeometry args={[0.12, 0.35, 0.13]} />
      </mesh>
      {/* Lower arms base */}
      <mesh position={[-0.54, 0.50, 0]} material={bodyMat}>
        <boxGeometry args={[0.10, 0.28, 0.10]} />
      </mesh>
      <mesh position={[0.54, 0.50, 0]} material={bodyMat}>
        <boxGeometry args={[0.10, 0.28, 0.10]} />
      </mesh>
      {/* Pelvis */}
      <mesh position={[0, 0.08, 0]} material={bodyMat}>
        <boxGeometry args={[0.44, 0.24, 0.28]} />
      </mesh>
      {/* Upper legs base */}
      <mesh position={[-0.18, -0.48, 0]} material={bodyMat}>
        <boxGeometry args={[0.21, 0.48, 0.21]} />
      </mesh>
      <mesh position={[0.18, -0.48, 0]} material={bodyMat}>
        <boxGeometry args={[0.21, 0.48, 0.21]} />
      </mesh>
      {/* Lower legs base */}
      <mesh position={[-0.16, -1.00, 0]} material={bodyMat}>
        <boxGeometry args={[0.14, 0.38, 0.14]} />
      </mesh>
      <mesh position={[0.16, -1.00, 0]} material={bodyMat}>
        <boxGeometry args={[0.14, 0.38, 0.14]} />
      </mesh>
      {/* Feet */}
      <mesh position={[-0.16, -1.24, 0.04]} material={bodyMat}>
        <boxGeometry args={[0.12, 0.06, 0.22]} />
      </mesh>
      <mesh position={[0.16, -1.24, 0.04]} material={bodyMat}>
        <boxGeometry args={[0.12, 0.06, 0.22]} />
      </mesh>

      {/* ── Interactive muscle overlays ────────────────── */}
      {MUSCLE_MESHES.map(({ id, pos, s }, i) => (
        <mesh
          key={`${id}-${i}`}
          position={pos}
          scale={s}
          material={materials[id]}
          onPointerDown={onClick(id)}
          onPointerOver={onOver(id)}
          onPointerOut={onOut}
        >
          <boxGeometry />
        </mesh>
      ))}
    </group>
  );
}
