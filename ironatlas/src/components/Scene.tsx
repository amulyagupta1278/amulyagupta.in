/**
 * Scene
 * ─────
 * R3F Canvas: camera, lighting, CameraControls, and the anatomy model.
 * Clicking empty canvas space clears selection (onPointerMissed).
 */
import { Suspense, useEffect, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { CameraControls, Environment } from '@react-three/drei';
import { useAnatomyStore } from '../store/useAnatomyStore';
import AnatomyModel from './AnatomyModel';
import type { CameraPreset } from '../types';

// Camera positions for each preset (eye x,y,z → target x,y,z)
const PRESETS: Record<CameraPreset, [number,number,number,number,number,number]> = {
  front: [ 0, 0.30,  3.6,  0, 0.30, 0],
  back:  [ 0, 0.30, -3.6,  0, 0.30, 0],
  left:  [-3.6, 0.30, 0,   0, 0.30, 0],
  right: [ 3.6, 0.30, 0,   0, 0.30, 0],
};

/** Inner component — must live inside <Canvas> to access useThree */
function CameraRig() {
  const ref    = useRef<CameraControls>(null);
  const preset = useAnatomyStore(s => s.cameraPreset);

  useEffect(() => {
    const ctrl = ref.current;
    if (!ctrl) return;
    const [ex, ey, ez, tx, ty, tz] = PRESETS[preset];
    // true = animate smoothly
    void ctrl.setLookAt(ex, ey, ez, tx, ty, tz, true);
  }, [preset]);

  return (
    <CameraControls
      ref={ref}
      makeDefault
      minDistance={1.2}
      maxDistance={8}
      // Restrict vertical orbit so model never flips
      minPolarAngle={Math.PI * 0.05}
      maxPolarAngle={Math.PI * 0.95}
    />
  );
}

export default function Scene() {
  return (
    <Canvas
      camera={{ position: [0, 0.30, 3.6], fov: 45 }}
      // Cap pixel ratio at 1.5 on mobile for perf
      dpr={[1, Math.min(window.devicePixelRatio, 1.5)]}
      style={{ position: 'absolute', inset: 0, top: 44 /* below topbar */ }}
      onPointerMissed={() => useAnatomyStore.getState().selectMuscle(null)}
    >
      {/* Background */}
      <color attach="background" args={['#0e0d11']} />

      {/* Lighting */}
      <ambientLight intensity={0.45} />
      <directionalLight position={[2, 5, 3]} intensity={1.6} castShadow={false} />
      <directionalLight position={[-2, 2, -3]} intensity={0.4} color="#9090c0" />
      <pointLight position={[0, 2, 2]} intensity={0.3} color="#c4864e" distance={6} />

      {/* Subtle environment reflections */}
      <Environment preset="city" background={false} environmentIntensity={0.15} />

      {/* Model */}
      <Suspense fallback={null}>
        <AnatomyModel />
      </Suspense>

      {/* Camera controls with preset support */}
      <CameraRig />
    </Canvas>
  );
}
