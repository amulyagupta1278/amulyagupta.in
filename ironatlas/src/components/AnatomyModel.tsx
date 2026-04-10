/**
 * AnatomyModel
 * ────────────
 * Top-level model switcher. Set MODEL_URL to your GLB path to activate
 * the real model; leave null to use the built-in placeholder.
 *
 * The GLBModel sub-component handles:
 *   • Auto-scale + auto-center via bounding box
 *   • Per-mesh material cloning
 *   • Emissive highlight & opacity on selection/hover
 *   • Raycasting via R3F pointer events
 */
import { useMemo, useEffect, useRef, Suspense } from 'react';
import { useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import type { ThreeEvent } from '@react-three/fiber';
import { useAnatomyStore } from '../store/useAnatomyStore';
import { getMuscleId } from '../data/meshMap';
import PlaceholderModel from './PlaceholderModel';

// ── Set this to your GLB path when ready ─────────────────
// e.g. './models/anatomy.glb'  (place file in ironatlas/public/models/)
const MODEL_URL: string | null = null;

// ── Highlight colours ─────────────────────────────────────
const C_SELECT = '#c4864e';
const C_HOVER  = '#5a3010';

export default function AnatomyModel() {
  if (!MODEL_URL) return <PlaceholderModel />;

  return (
    <Suspense fallback={null}>
      <GLBModel url={MODEL_URL} />
    </Suspense>
  );
}

// ── GLB loader + interaction ──────────────────────────────
function GLBModel({ url }: { url: string }) {
  const { scene } = useGLTF(url);
  const groupRef  = useRef<THREE.Group>(null);

  const selected     = useAnatomyStore(s => s.selectedMuscle);
  const hovered      = useAnatomyStore(s => s.hoveredMuscle);
  const selectMuscle = useAnatomyStore(s => s.selectMuscle);
  const hoverMuscle  = useAnatomyStore(s => s.hoverMuscle);

  // ── Clone + auto-center + scale ──────────────────────────
  const { clonedScene, scale, offset } = useMemo(() => {
    const clone = scene.clone(true);

    // Give every muscle mesh its own material + userData
    clone.traverse(obj => {
      if (!(obj instanceof THREE.Mesh)) return;
      const mId = getMuscleId(obj.name);
      if (!mId) return;
      obj.material = new THREE.MeshStandardMaterial({
        color:      new THREE.Color('#2e2a3d'),
        roughness:  0.72,
        metalness:  0.08,
        transparent: true,
        opacity:     1,
      });
      obj.userData.muscleId = mId;
    });

    // Auto-center and scale to fit a ~2.5-unit tall bounding box
    const box    = new THREE.Box3().setFromObject(clone);
    const center = box.getCenter(new THREE.Vector3());
    const size   = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z);

    return {
      clonedScene: clone,
      scale:  2.5 / maxDim,
      offset: center.negate(),
    };
  }, [scene]);

  // ── Update materials on state change ─────────────────────
  useEffect(() => {
    clonedScene.traverse(obj => {
      if (!(obj instanceof THREE.Mesh) || !obj.userData.muscleId) return;
      const id  = obj.userData.muscleId as string;
      const mat = obj.material as THREE.MeshStandardMaterial;
      const isSel = selected === id;
      const isHov = hovered  === id;
      mat.emissive.set(isSel ? C_SELECT : isHov ? C_HOVER : '#000000');
      mat.emissiveIntensity = isSel ? 0.90 : isHov ? 0.45 : 0;
      mat.opacity = selected && !isSel ? 0.18 : 1.0;
    });
  }, [selected, hovered, clonedScene]);

  // ── Cleanup ───────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clonedScene.traverse(obj => {
        if (obj instanceof THREE.Mesh && obj.userData.muscleId) {
          (obj.material as THREE.MeshStandardMaterial).dispose();
        }
      });
    };
  }, [clonedScene]);

  const onClick = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    const id = (e.object as THREE.Mesh).userData.muscleId as string | undefined;
    if (id) selectMuscle(selected === id ? null : id);
  };
  const onOver = (e: ThreeEvent<PointerEvent>) => {
    e.stopPropagation();
    const id = (e.object as THREE.Mesh).userData.muscleId as string | undefined;
    if (id) { hoverMuscle(id); document.body.style.cursor = 'pointer'; }
  };
  const onOut = () => { hoverMuscle(null); document.body.style.cursor = 'default'; };

  return (
    <group ref={groupRef} scale={scale} position={[offset.x, offset.y, offset.z]}>
      <primitive
        object={clonedScene}
        onPointerDown={onClick}
        onPointerOver={onOver}
        onPointerOut={onOut}
      />
    </group>
  );
}
