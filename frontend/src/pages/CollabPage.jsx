import { useState, useEffect } from 'react';
import { recApi } from '../services/api';
import TrackCard from '../components/TrackCard/TrackCard';

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

export default function CollabPage() {
  const [tracks,  setTracks]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const fetchRecs = async () => {
    setLoading(true); setError('');
    try {
      const res = await recApi.collab();
      setTracks(res.data ?? []);
    } catch {
      setError('Failed to load collaborative recommendations.');
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchRecs(); }, []);

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="page-header-badge">Collaborative Filtering</div>
        <h1 className="page-title">Collab Picks</h1>
        <p className="page-subtitle">
          Được gợi ý dựa trên người dùng có gu âm nhạc giống bạn
        </p>
      </div>

      <div className="section-header">
        <div>
          <div className="section-title">Từ cộng đồng nghe nhạc</div>
          <div className="section-subtitle">
            Thuật toán ALS · Matrix Factorization
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={fetchRecs} disabled={loading}>
          {loading ? <span className="spin">⟳</span> : '↻ Refresh'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? <SkeletonGrid /> : tracks.length === 0 ? (
        <div className="empty-state">
          <div className="icon">🤝</div>
          <h3>Chưa có gợi ý Collaborative</h3>
          <p>Hãy nghe thêm nhạc để hệ thống hiểu gu của bạn!</p>
        </div>
      ) : (
        <div className="tracks-grid">
          {tracks.map(t => t && <TrackCard key={t._id} track={t} />)}
        </div>
      )}
    </div>
  );
}
