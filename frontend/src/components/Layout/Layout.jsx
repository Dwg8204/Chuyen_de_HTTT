import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import MusicPlayer from '../MusicPlayer/MusicPlayer';
import RecommendPopup from '../RecommendPopup/RecommendPopup';
import { usePlayer } from '../../contexts/PlayerContext';

export default function Layout() {
  const { showPopup } = usePlayer();
  return (
    <div className="app-layout">
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
      <MusicPlayer />
      {showPopup && <RecommendPopup />}
    </div>
  );
}
