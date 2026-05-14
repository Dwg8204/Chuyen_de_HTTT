import { useState } from 'react';
import { usersApi } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const GENRES = [
  { id: 'pop',        label: '🎵 Pop' },
  { id: 'rock',       label: '🎸 Rock' },
  { id: 'rnb',        label: '🎶 R&B' },
  { id: 'indie',      label: '🌿 Indie' },
  { id: 'acoustic',   label: '🪕 Acoustic' },
  { id: 'hiphop',     label: '🎤 Hip-Hop' },
  { id: 'jazz',       label: '🎷 Jazz' },
  { id: 'electronic', label: '🎛️ Electronic' },
  { id: 'classical',  label: '🎻 Classical' },
  { id: 'kpop',       label: '✨ K-Pop' },
  { id: 'vpop',       label: '🇻🇳 V-Pop' },
  { id: 'metal',      label: '🤘 Metal' },
];

const POPULAR_ARTISTS = [
  'Taylor Swift', 'Ed Sheeran', 'Drake', 'Billie Eilish', 'The Weeknd',
  'Ariana Grande', 'Post Malone', 'Dua Lipa', 'BTS', 'Coldplay',
  'Eminem', 'Lady Gaga', 'Bruno Mars', 'Adele', 'Justin Bieber',
  'Sơn Tùng M-TP', 'Mỹ Tâm', 'Đen Vâu',
];

export default function ProfilePage() {
  const { user, refreshUser } = useAuth();

  // Demographics form
  const [form, setForm] = useState({
    age:      user?.demographics?.age      ?? '',
    gender:   user?.demographics?.gender   ?? '',
    location: user?.demographics?.location ?? '',
  });

  // Genres & artists (editable)
  const [genres,    setGenres]    = useState(user?.onboarding_preferences?.favorite_genres  ?? []);
  const [artists,   setArtists]   = useState(user?.onboarding_preferences?.favorite_artists ?? []);
  const [artistQ,   setArtistQ]   = useState('');
  const [editPrefs, setEditPrefs] = useState(false);

  const [msg,     setMsg]     = useState('');
  const [loading, setLoading] = useState(false);

  const toggleGenre  = (id)   => setGenres(p  => p.includes(id)   ? p.filter(g => g !== id)   : [...p, id]);
  const toggleArtist = (name) => setArtists(p => p.includes(name) ? p.filter(a => a !== name) : [...p, name]);
  const addCustomArtist = () => {
    const name = artistQ.trim();
    if (name && !artists.includes(name)) setArtists(p => [...p, name]);
    setArtistQ('');
  };

  const handleSaveDemo = async (e) => {
    e.preventDefault();
    setLoading(true); setMsg('');
    try {
      await usersApi.updateProfile(form);
      await refreshUser();
      setMsg('✅ Profile updated!');
    } catch { setMsg('❌ Failed to update.'); }
    finally { setLoading(false); }
  };

  const handleSavePrefs = async () => {
    setLoading(true); setMsg('');
    try {
      await usersApi.updateOnboarding({
        favorite_genres:  genres,
        favorite_artists: artists,
        mood: user?.onboarding_preferences?.mood ?? '',
      });
      await refreshUser();
      setMsg('✅ Preferences saved!');
      setEditPrefs(false);
    } catch { setMsg('❌ Failed to save preferences.'); }
    finally { setLoading(false); }
  };

  const avatar  = (user?.username ?? 'U')[0].toUpperCase();
  const mood    = user?.onboarding_preferences?.mood;
  const filteredSuggestions = POPULAR_ARTISTS.filter(
    a => a.toLowerCase().includes(artistQ.toLowerCase()) && !artists.includes(a)
  );

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Profile</h1>
        <p className="page-subtitle">Manage your account and music preferences</p>
      </div>

      {msg && (
        <div className={`alert ${msg.startsWith('✅') ? 'alert-success' : 'alert-error'}`} style={{ marginBottom: 20 }}>
          {msg}
        </div>
      )}

      {/* ── Profile Card ── */}
      <div className="profile-card">
        <div className="profile-avatar">{avatar}</div>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: 4 }}>{user?.username}</h2>
        <span className={`badge badge-${user?.role}`}>{user?.role}</span>
        {mood && (
          <div style={{ marginTop: 8, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Current mood: <strong style={{ color: 'var(--text-primary)' }}>{mood}</strong>
          </div>
        )}
      </div>

      {/* ── Music Preferences ── */}
      <div className="admin-section" style={{ marginTop: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <div className="admin-section-title" style={{ margin: 0 }}>🎵 Music Preferences</div>
          <button
            className={`btn ${editPrefs ? 'btn-ghost' : 'btn-primary'} btn-sm`}
            onClick={() => { setEditPrefs(e => !e); setMsg(''); }}
          >
            {editPrefs ? '✕ Cancel' : '✏️ Edit Preferences'}
          </button>
        </div>

        {/* View mode */}
        {!editPrefs && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {/* Genres */}
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 10, letterSpacing: '0.05em' }}>
                FAVOURITE GENRES
              </div>
              {genres.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {genres.map(g => {
                    const found = GENRES.find(x => x.id === g);
                    return (
                      <span key={g} style={{
                        background: 'var(--bg-elevated)', border: '1px solid var(--accent)',
                        color: 'var(--accent)', borderRadius: 20, padding: '4px 14px',
                        fontSize: '0.82rem', fontWeight: 600,
                      }}>
                        {found ? found.label : g}
                      </span>
                    );
                  })}
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  No genres selected — click "Edit Preferences" to add some
                </div>
              )}
            </div>

            {/* Artists */}
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 10, letterSpacing: '0.05em' }}>
                FAVOURITE ARTISTS
              </div>
              {artists.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {artists.map(a => (
                    <span key={a} style={{
                      background: 'var(--bg-elevated)', border: '1px solid #6c63ff',
                      color: '#6c63ff', borderRadius: 20, padding: '4px 14px',
                      fontSize: '0.82rem', fontWeight: 600,
                    }}>🎤 {a}</span>
                  ))}
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  No artists selected — click "Edit Preferences" to add some
                </div>
              )}
            </div>
          </div>
        )}

        {/* Edit mode */}
        {editPrefs && (
          <div>
            {/* Genre selection */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.05em' }}>
                CHOOSE GENRES ({genres.length} selected)
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {GENRES.map(g => (
                  <button
                    key={g.id}
                    onClick={() => toggleGenre(g.id)}
                    style={{
                      padding: '7px 16px', borderRadius: 20, border: '1px solid',
                      cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600,
                      transition: 'all 0.15s',
                      borderColor: genres.includes(g.id) ? 'var(--accent)' : 'var(--border)',
                      background:  genres.includes(g.id) ? 'var(--accent)' : 'var(--bg-elevated)',
                      color:       genres.includes(g.id) ? '#000' : 'var(--text-secondary)',
                    }}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Artist search */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.05em' }}>
                SEARCH ARTISTS ({artists.length} selected)
              </div>

              <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
                <input
                  className="form-input"
                  placeholder="Type an artist name to search or add…"
                  value={artistQ}
                  onChange={e => setArtistQ(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomArtist(); } }}
                  style={{ flex: 1 }}
                />
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={addCustomArtist}
                  disabled={!artistQ.trim()}
                  style={{ whiteSpace: 'nowrap' }}
                >
                  + Add
                </button>
              </div>

              {/* Dropdown suggestions */}
              {artistQ && filteredSuggestions.length > 0 && (
                <div style={{
                  background: 'var(--bg-base)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', marginBottom: 12,
                  maxHeight: 160, overflowY: 'auto',
                }}>
                  {filteredSuggestions.slice(0, 8).map(a => (
                    <div
                      key={a}
                      onClick={() => { toggleArtist(a); setArtistQ(''); }}
                      style={{
                        padding: '9px 14px', cursor: 'pointer',
                        borderBottom: '1px solid var(--border)',
                        fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8,
                      }}
                      className="artist-suggestion-item"
                    >
                      <span>🎤</span> {a}
                    </div>
                  ))}
                </div>
              )}

              {/* Popular artists grid (when not searching) */}
              {!artistQ && (
                <div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                    POPULAR — click to select:
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {POPULAR_ARTISTS.map(a => (
                      <button
                        key={a}
                        onClick={() => toggleArtist(a)}
                        style={{
                          padding: '5px 12px', borderRadius: 20, border: '1px solid',
                          cursor: 'pointer', fontSize: '0.78rem', fontWeight: 500,
                          transition: 'all 0.15s',
                          borderColor: artists.includes(a) ? '#6c63ff' : 'var(--border)',
                          background:  artists.includes(a) ? '#6c63ff' : 'var(--bg-elevated)',
                          color:       artists.includes(a) ? '#fff'    : 'var(--text-secondary)',
                        }}
                      >
                        {artists.includes(a) ? '✓ ' : ''}{a}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Selected artists chips */}
              {artists.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: '0.72rem', color: '#6c63ff', fontWeight: 700, marginBottom: 8 }}>
                    ✓ SELECTED ARTISTS:
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {artists.map(a => (
                      <div key={a} style={{
                        display: 'flex', alignItems: 'center', gap: 5,
                        background: '#6c63ff', color: '#fff',
                        borderRadius: 20, padding: '4px 12px',
                        fontSize: '0.78rem', fontWeight: 600,
                      }}>
                        {a}
                        <span
                          onClick={() => toggleArtist(a)}
                          style={{ cursor: 'pointer', opacity: 0.8, fontWeight: 700 }}
                        >×</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <button className="btn btn-primary" onClick={handleSavePrefs} disabled={loading}>
              {loading ? <span className="spin">⟳</span> : '💾 Save Preferences'}
            </button>
          </div>
        )}
      </div>

      {/* ── Demographics ── */}
      <div className="admin-section" style={{ marginTop: 20 }}>
        <div className="admin-section-title">👤 Personal Info</div>
        <form onSubmit={handleSaveDemo}>
          <div className="profile-grid">
            <div className="form-group">
              <label>Age</label>
              <input className="form-input" type="number" placeholder="Your age"
                value={form.age} onChange={e => setForm(f => ({ ...f, age: e.target.value }))} />
            </div>
            <div className="form-group">
              <label>Gender</label>
              <select className="form-input" style={{ cursor: 'pointer' }}
                value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))}>
                <option value="">Select</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label>Location</label>
            <input className="form-input" placeholder="e.g. Vietnam, US, UK"
              value={form.location} onChange={e => setForm(f => ({ ...f, location: e.target.value }))} />
          </div>
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? <span className="spin">⟳</span> : 'Save Changes'}
          </button>
        </form>
      </div>
    </div>
  );
}
