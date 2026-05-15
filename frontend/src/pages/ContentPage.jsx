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

export default function ContentPage() {
  const [tracks,  setTracks]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const fetchRecs = async () => {
    setLoading(true); setError('');
    try {
      const res = await recApi.content();
      setTracks(res.data ?? []);
    } catch {
      setError('Failed to load content-based recommendations.');
    } finally { setLoading(false); }
  };

  useEffect(() => { fetchRecs(); }, []);

  return (
    <div className="fade-in">
      <div className="page-header">
        <div className="page-header-badge">Content-Based Filtering</div>
        <h1 className="page-title">Taste Match</h1>
        <p className="page-subtitle">
          Gợi ý dựa trên âm thanh và phong cách nhạc bạn vừa nghe
        </p>
      </div>

      <div className="section-header">
        <div>
          <div className="section-title">Khám phá âm nhạc giống gu bạn</div>
          <div className="section-subtitle">
            Thuật toán Content-Based · Cosine Similarity trên Audio Features
          </div>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={fetchRecs} disabled={loading}>
          {loading ? <span className="spin">⟳</span> : '↻ Refresh'}
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {loading ? <SkeletonGrid /> : tracks.length === 0 ? (
        <div className="empty-state">
          <div className="icon">🎨</div>
          <h3>Chưa có gợi ý Content-Based</h3>
          <p>Hãy nghe vài bài để hệ thống phân tích âm thanh của bạn!</p>
        </div>
      ) : (
        <div className="tracks-grid">
          {tracks.map(t => t && <TrackCard key={t._id} track={t} />)}
        </div>
      )}
    </div>
  );
}
