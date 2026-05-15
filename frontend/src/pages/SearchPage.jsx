import { useState, useCallback, useEffect, useRef } from 'react';
import { tracksApi } from '../services/api';
import TrackCard from '../components/TrackCard/TrackCard';

export default function SearchPage() {
  const [query,    setQuery]    = useState('');
  const [genre,    setGenre]    = useState('');
  const [genres,   setGenres]   = useState([]);
  const [tracks,   setTracks]   = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [searched, setSearched] = useState(false);
  const [error,    setError]    = useState('');
  const inputRef = useRef(null);

  // Load danh sách genre từ DB
  useEffect(() => {
    tracksApi.genres()
      .then(res => setGenres(Array.isArray(res.data) ? res.data : []))
      .catch(() => {});
  }, []);

  const doSearch = useCallback(async (q, g) => {
    const term = (q ?? query).trim();
    if (!term && !g) return;
    setLoading(true);
    setError('');
    try {
      const res = await tracksApi.search(term, 40, g || genre || undefined);
      const list = Array.isArray(res.data) ? res.data : (res.data?.data ?? []);
      setTracks(list);
      setSearched(true);
    } catch (err) {
      setError(err.response?.data?.message ?? 'Search failed.');
      setTracks([]);
    } finally {
      setLoading(false);
    }
  }, [query, genre]);

  const handleSubmit = (e) => { e.preventDefault(); doSearch(query, genre); };

  // Khi chọn genre → tự động tìm kiếm ngay
  const handleGenreChange = (g) => {
    setGenre(g);
    doSearch(query, g);
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Search</h1>
        <p className="page-subtitle">Tìm bài hát, nghệ sĩ — hỗ trợ cả tiếng Việt không dấu</p>
      </div>

      <div className="section-header" style={{ marginBottom: 12 }}>
        <div className="section-title" style={{ fontSize: '1.1rem' }}>Tìm bài hát hoặc nghệ sĩ</div>
      </div>
      {/* Search bar */}
      <form className="search-bar" onSubmit={handleSubmit}>
        <svg width="20" height="20" fill="var(--text-muted)" viewBox="0 0 24 24">
          <path d="M15.5 14h-.79l-.28-.27A6.5 6.5 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        <input
          ref={inputRef}
          id="search-input"
          placeholder='Gõ tên bài hát hoặc tên ca sĩ (hỗ trợ tìm không dấu)...'
          value={query}
          onChange={e => setQuery(e.target.value)}
          autoFocus
        />
        <button
          id="search-btn"
          className="btn btn-primary btn-sm"
          type="submit"
          disabled={loading || (!query.trim() && !genre)}
        >
          {loading ? <span className="spin">⟳</span> : 'Search'}
        </button>
      </form>

      {/* Genre filter chips */}
      {genres.length > 0 && (
        <div style={{ marginTop: 24, padding: '20px', background: 'var(--bg-card)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--border)' }}>
          <div className="section-title" style={{ fontSize: '1.1rem', marginBottom: 16 }}>Khám phá theo thể loại</div>
          <div className="genre-filter-row" style={{ marginBottom: 0 }}>
            <button
              className={`genre-chip${genre === '' ? ' active' : ''}`}
              onClick={() => handleGenreChange('')}
            >
              Tất cả
            </button>
            {genres.map(g => (
              <button
                key={g}
                className={`genre-chip${genre === g ? ' active' : ''}`}
                onClick={() => handleGenreChange(genre === g ? '' : g)}
              >
                {g}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-error" style={{ marginTop: 16 }}>
          ⚠️ {error}
        </div>
      )}

      {loading && (
        <div className="loading-grid" style={{ marginTop: 24 }}>
          {Array(8).fill(0).map((_, i) => (
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
          <h3>Không tìm thấy kết quả</h3>
          <p>Thử từ khác hoặc bỏ bộ lọc thể loại</p>
        </div>
      )}

      {!loading && tracks.length > 0 && (
        <>
          <div className="section-header" style={{ marginBottom: 16, marginTop: 24 }}>
            <div className="section-title">
              {tracks.length} kết quả{query ? ` cho "${query}"` : ''}{genre ? ` · ${genre}` : ''}
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
          <h3>Bắt đầu tìm kiếm</h3>
          <p>Gõ tên bài hát hoặc nghệ sĩ, hoặc chọn thể loại bên trên</p>
        </div>
      )}
    </div>
  );
}
