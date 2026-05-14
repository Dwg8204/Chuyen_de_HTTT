import { useState, useEffect } from 'react';
import { recApi } from '../services/api';
import TrackCard from '../components/TrackCard/TrackCard';
import { useAuth } from '../contexts/AuthContext';

function SkeletonGrid() {
  return (
    <div className="loading-grid">
      {Array(10).fill(0).map((_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton-artwork" />
          <div className="skeleton-line" />
          <div className="skeleton-line short" />
        </div>
      ))}
    </div>
  );
}

export default function HomePage() {
  const { user } = useAuth();
  const [tracks,  setTracks]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const fetchRecs = async () => {
    setLoading(true); setError('');
    try {
      const res = await recApi.hybrid();
      setTracks(res.data ?? []);
    } catch {
      setError('Failed to load recommendations. Make sure the backend is running.');
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchRecs(); }, []);

  const genres = user?.onboarding_preferences?.favorite_genres ?? [];

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Good evening, {user?.username} 👋</h1>
        <p className="page-subtitle">
          {genres.length > 0
            ? `Personalized picks for you · ${genres.map(g => g.charAt(0).toUpperCase() + g.slice(1)).join(', ')}`
            : 'Your personalized music recommendations'}
        </p>
      </div>

      <div className="section-header">
        <div>
          <div className="section-title">Made For You</div>
          <div className="section-subtitle" style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
            Powered by your listening history + preferences
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={fetchRecs} disabled={loading}>
          {loading ? <span className="spin">⟳</span> : '↻ Refresh'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? <SkeletonGrid /> : tracks.length === 0 ? (
        <div className="empty-state">
          <div className="icon">🎵</div>
          <h3>No recommendations yet</h3>
          <p>Start listening to some tracks and come back!</p>
        </div>
      ) : (
        <div className="tracks-grid">
          {tracks.map(t => t && <TrackCard key={t._id} track={t} />)}
        </div>
      )}
    </div>
  );
}
