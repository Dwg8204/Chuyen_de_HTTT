import { useState, useCallback, useRef } from 'react';
import { tracksApi } from '../services/api';
import TrackCard from '../components/TrackCard/TrackCard';

export default function SearchPage() {
  const [query,    setQuery]    = useState('');
  const [tracks,   setTracks]   = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [searched, setSearched] = useState(false);
  const [error,    setError]    = useState('');
  const inputRef = useRef(null);

  const doSearch = useCallback(async (q) => {
    const term = q.trim();
    if (!term) return;
    setLoading(true);
    setError('');
    try {
      const res = await tracksApi.search(term, 30);
      // NestJS trả về array trực tiếp hoặc { data: [] }
      const list = Array.isArray(res.data) ? res.data : (res.data?.data ?? []);
      setTracks(list);
      setSearched(true);
    } catch (err) {
      setError(err.response?.data?.message ?? 'Search failed. Make sure backend is running.');
      setTracks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    doSearch(query);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') doSearch(query);
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Search</h1>
        <p className="page-subtitle">Find songs, artists and more</p>
      </div>

      <form className="search-bar" onSubmit={handleSubmit}>
        <svg width="20" height="20" fill="var(--text-muted)" viewBox="0 0 24 24">
          <path d="M15.5 14h-.79l-.28-.27A6.5 6.5 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        <input
          ref={inputRef}
          id="search-input"
          placeholder="Search for songs or artists…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />
        <button
          id="search-btn"
          className="btn btn-primary btn-sm"
          type="submit"
          disabled={loading || !query.trim()}
        >
          {loading ? <span className="spin">⟳</span> : 'Search'}
        </button>
      </form>

      {error && (
        <div className="alert alert-error" style={{ marginTop: 16 }}>
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div className="loading-grid" style={{ marginTop: 24 }}>
          {Array(6).fill(0).map((_, i) => (
            <div key={i} className="skeleton-card">
              <div className="skeleton-artwork" />
              <div className="skeleton-line" />
              <div className="skeleton-line short" />
            </div>
          ))}
        </div>
      )}

      {!loading && searched && tracks.length === 0 && !error && (
        <div className="empty-state">
          <div className="icon">🔍</div>
          <h3>No results for "{query}"</h3>
          <p>Try a different search term or check if the backend is running</p>
        </div>
      )}

      {!loading && tracks.length > 0 && (
        <>
          <div className="section-header" style={{ marginBottom: 16, marginTop: 24 }}>
            <div className="section-title">
              {tracks.length} results for "<em>{query}</em>"
            </div>
          </div>
          <div className="tracks-grid">
            {tracks.map(t => <TrackCard key={t._id} track={t} />)}
          </div>
        </>
      )}

      {!searched && !loading && (
        <div className="empty-state" style={{ marginTop: 48 }}>
          <div className="icon">🎵</div>
          <h3>Start searching</h3>
          <p>Type a song name or artist above and press Search</p>
        </div>
      )}
    </div>
  );
}
