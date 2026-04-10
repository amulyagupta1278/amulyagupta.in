import Scene from './components/Scene';
import MuscleInfoPanel from './components/MuscleInfoPanel';
import ViewControls from './components/ViewControls';
import { useAnatomyStore } from './store/useAnatomyStore';

function Topbar() {
  const selected = useAnatomyStore(s => s.selectedMuscle);
  return (
    <header className="topbar">
      <div className="topbar__logo">
        <div className="topbar__mark" />
        Iron<span className="a">Atlas</span>
      </div>
      <span className="topbar__hint">
        {selected ? 'Click to deselect · drag to rotate' : '3D Muscle Explorer'}
      </span>
    </header>
  );
}

export default function App() {
  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <Topbar />
      <Scene />
      <MuscleInfoPanel />
      <ViewControls />
    </div>
  );
}
