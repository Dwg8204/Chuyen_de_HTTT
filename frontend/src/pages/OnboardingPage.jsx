import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usersApi, tracksApi } from '../services/api';
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

const MOODS = [
  { id: 'energetic',   icon: '⚡', label: 'Energetic' },
  { id: 'chill',       icon: '😌', label: 'Chill' },
  { id: 'happy',       icon: '😊', label: 'Happy' },
  { id: 'melancholic', icon: '🌧️', label: 'Melancholic' },
  { id: 'focused',     icon: '🎯', label: 'Focused' },
  { id: 'romantic',    icon: '💝', label: 'Romantic' },
];

const POPULAR_ARTISTS = [
  'Taylor Swift', 'Ed Sheeran', 'Drake', 'Billie Eilish', 'The Weeknd',
  'Ariana Grande', 'Post Malone', 'Dua Lipa', 'BTS', 'Coldplay',
  'Eminem', 'Lady Gaga', 'Bruno Mars', 'Adele', 'Justin Bieber',
];

const STEPS = ['genres', 'mood', 'artists'];

export default function OnboardingPage() {
  const { refreshUser } = useAuth();
  const navigate        = useNavigate();

  const [step,    setStep]    = useState(0);
  const [genres,  setGenres]  = useState([]);
  const [mood,    setMood]    = useState('');
  const [artists, setArtists] = useState([]);   // selected artist names
  const [artistQ, setArtistQ] = useState('');   // search input
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  const toggleGenre  = (id) => setGenres(p  => p.includes(id) ? p.filter(g => g !== id) : [...p, id]);
  const toggleArtist = (name) => setArtists(p => p.includes(name) ? p.filter(a => a !== name) : [...p, name]);

  const addCustomArtist = () => {
    const name = artistQ.trim();
    if (name && !artists.includes(name)) {
      setArtists(p => [...p, name]);
    }
    setArtistQ('');
  };

  const canNext = () => {
    if (step === 0) return genres.length > 0;
    if (step === 1) return !!mood;
    return true;
  };

  const handleNext = () => {
    setError('');
    if (step < STEPS.length - 1) { setStep(s => s + 1); return; }
    handleSubmit();
  };

  const handleBack = () => { setError(''); setStep(s => s - 1); };

  const handleSubmit = async () => {
    setLoading(true); setError('');
    try {
      await usersApi.updateOnboarding({
        favorite_genres:  genres,
        mood,
        favorite_artists: artists,
      });
      await refreshUser();
      navigate('/');
    } catch {
      setError('Failed to save preferences. Please try again.');
    } finally { setLoading(false); }
  };

  const filtered = POPULAR_ARTISTS.filter(a =>
    a.toLowerCase().includes(artistQ.toLowerCase()) && !artists.includes(a)
  );

  const stepLabels = ['Genres', 'Mood', 'Artists'];

  return (
    <div className="onboarding-page">
      <div className="onboarding-card" style={{ maxWidth: 560 }}>
        {/* Logo */}
        <div className="auth-logo">🎵 MUSICREC</div>
        <h1 style={{ marginBottom: 4 }}>Personalize Your Experience</h1>
        <p style={{ color: 'var(--text-muted)', marginBottom: 24 }}>
          Step {step + 1} of {STEPS.length} — {step === 0 ? 'Choose your favourite genres' : step === 1 ? 'Pick your current mood' : 'Add artists you love'}
        </p>

        {/* Progress dots */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 28 }}>
          {stepLabels.map((l, i) => (
            <div key={l} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: '0.75rem', fontWeight: i === step ? 700 : 400,
              color: i <= step ? 'var(--accent)' : 'var(--text-muted)',
            }}>
              <div style={{
                width: 24, height: 24, borderRadius: '50%', display: 'flex',
                alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem',
                background: i < step ? 'var(--accent)' : i === step ? 'var(--accent)' : 'var(--bg-elevated)',
                color: i <= step ? '#000' : 'var(--text-muted)',
                fontWeight: 700,
              }}>
                {i < step ? '✓' : i + 1}
              </div>
              {l}
              {i < stepLabels.length - 1 && (
                <div style={{ width: 20, height: 2, background: i < step ? 'var(--accent)' : 'var(--bg-elevated)' }} />
              )}
            </div>
          ))}
        </div>

        {/* ── Step 0: Genres ── */}
        {step === 0 && (
          <>
            <div className="section-label">GENRES (select at least 1)</div>
            <div className="genre-grid">
              {GENRES.map(g => (
                <button
                  key={g.id}
                  className={`genre-btn${genres.includes(g.id) ? ' selected' : ''}`}
                  onClick={() => toggleGenre(g.id)}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </>
        )}

        {/* ── Step 1: Mood ── */}
        {step === 1 && (
          <>
            <div className="section-label">YOUR CURRENT MOOD</div>
            <div className="mood-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
              {MOODS.map(m => (
                <button
                  key={m.id}
                  className={`mood-btn${mood === m.id ? ' selected' : ''}`}
                  onClick={() => setMood(m.id)}
                  style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '14px 8px' }}
                >
                  <span style={{ fontSize: '1.4rem' }}>{m.icon}</span>
                  <span>{m.label}</span>
                </button>
              ))}
            </div>
          </>
        )}

        {/* ── Step 2: Artists ── */}
        {step === 2 && (
          <>
            <div className="section-label">FAVOURITE ARTISTS (optional)</div>

            {/* Search + add custom */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <input
                className="input"
                placeholder="Search or type an artist name…"
                value={artistQ}
                onChange={e => setArtistQ(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addCustomArtist(); } }}
                style={{ flex: 1 }}
              />
              <button className="btn btn-ghost btn-sm" onClick={addCustomArtist} disabled={!artistQ.trim()}>
                Add
              </button>
            </div>

            {/* Suggestions */}
            {filtered.length > 0 && artistQ && (
              <div style={{
                background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)',
                marginBottom: 12, maxHeight: 140, overflowY: 'auto',
              }}>
                {filtered.slice(0, 8).map(a => (
                  <div key={a}
                    onClick={() => { toggleArtist(a); setArtistQ(''); }}
                    style={{
                      padding: '8px 12px', cursor: 'pointer',
                      borderBottom: '1px solid var(--border)',
                      fontSize: '0.85rem',
                    }}
                    className="artist-suggestion"
                  >
                    🎤 {a}
                  </div>
                ))}
              </div>
            )}

            {/* Popular artists grid */}
            {!artistQ && (
              <>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                  POPULAR ARTISTS
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
                  {POPULAR_ARTISTS.filter(a => !artists.includes(a)).map(a => (
                    <button key={a}
                      className="genre-btn"
                      onClick={() => toggleArtist(a)}
                      style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* Selected artists */}
            {artists.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--accent)', marginBottom: 8, fontWeight: 600 }}>
                  ✓ SELECTED ({artists.length})
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {artists.map(a => (
                    <div key={a} style={{
                      display: 'flex', alignItems: 'center', gap: 6,
                      background: 'var(--accent)', color: '#000',
                      borderRadius: 20, padding: '4px 12px', fontSize: '0.78rem', fontWeight: 600,
                    }}>
                      {a}
                      <span
                        onClick={() => toggleArtist(a)}
                        style={{ cursor: 'pointer', fontWeight: 700, fontSize: '0.9rem' }}
                      >×</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {error && <div className="alert alert-error" style={{ marginTop: 16 }}>{error}</div>}

        {/* Navigation buttons */}
        <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
          {step > 0 && (
            <button className="btn btn-ghost" onClick={handleBack} style={{ flex: 1 }}>
              ← Back
            </button>
          )}
          <button
            className="btn btn-primary"
            onClick={handleNext}
            disabled={loading || !canNext()}
            style={{ flex: 2 }}
          >
            {loading
              ? <span className="spin">⟳</span>
              : step < STEPS.length - 1
                ? 'Next →'
                : "Let's Go! 🚀"}
          </button>
        </div>

        {step === STEPS.length - 1 && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleSubmit}
            style={{ width: '100%', marginTop: 8, fontSize: '0.78rem', color: 'var(--text-muted)' }}
          >
            Skip for now
          </button>
        )}
      </div>
    </div>
  );
}
