import { useState, useEffect } from 'react';
import { adminApi } from '../services/api';

// ── Reusable MetricsCard ───────────────────────────────────────────────────────
function MetricsCard({ metrics, modelLabel, color, running, onRun, btnLabel }) {
  return (
    <div className="metrics-card" style={{ borderLeft: `3px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: '1rem' }}>{modelLabel}</div>
          {metrics?.users_evaluated && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
              Evaluated on {metrics.users_evaluated} users · 80/20 time-split
            </div>
          )}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={onRun} disabled={running}>
          {running ? <><span className="spin">⟳</span> Running…</> : btnLabel}
        </button>
      </div>

      {metrics?.error && (
        <div className="alert alert-error">{metrics.error}</div>
      )}

      {metrics && !metrics.error && (
        <div className="metrics-row">
          {[
            { label: 'NDCG@10',    val: metrics.ndcg_at_10 },
            { label: 'Recall@10',  val: metrics.recall_at_10 },
            { label: 'Recall@20',  val: metrics.recall_at_20 },
            { label: 'Prec@10',    val: metrics.precision_at_10 },
            { label: 'Prec@20',    val: metrics.precision_at_20 },
            { label: 'Coverage',   val: metrics.coverage },
          ].map(m => (
            <div key={m.label} className="metric-item">
              <div className="metric-value" style={{ color, fontSize: '1.5rem' }}>
                {m.val !== undefined ? (m.val * 100).toFixed(1) + '%' : '—'}
              </div>
              <div className="metric-label">{m.label}</div>
            </div>
          ))}
        </div>
      )}

      {!metrics && !running && (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '12px 0' }}>
          Click "{btnLabel}" to compute metrics
        </div>
      )}
    </div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function AdminDashboard() {
  const [stats,     setStats]     = useState(null);
  const [users,     setUsers]     = useState([]);
  const [cfMetrics, setCfMetrics] = useState(null);
  const [cbMetrics, setCbMetrics] = useState(null);
  const [training,  setTraining]  = useState(false);
  const [cfLoading, setCfLoading] = useState(false);
  const [cbLoading, setCbLoading] = useState(false);
  const [msg,       setMsg]       = useState('');

  useEffect(() => {
    adminApi.stats().then(r => setStats(r.data)).catch(() => {});
    adminApi.listUsers(1, 20).then(r => setUsers(r.data.users ?? [])).catch(() => {});
  }, []);

  const handleTrain = async () => {
    setTraining(true); setMsg('⏳ Training started in background...');
    try {
      await adminApi.triggerTraining();
      // Poll /ai/train/status until done
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        try {
          const statusRes = await adminApi.trainStatus();
          const s = statusRes.data;
          if (s.status === 'done') {
            clearInterval(poll);
            setTraining(false);
            const r = s.result ?? {};
            setMsg(`✅ ALS Training complete! ${r.users_processed ?? '?'} users | ${r.items ?? '?'} items | ${r.duration_seconds ?? '?'}s`);
          } else if (s.status === 'error') {
            clearInterval(poll);
            setTraining(false);
            setMsg(`❌ Training failed: ${s.message}`);
          } else if (attempts > 120) { // 6 phút timeout
            clearInterval(poll);
            setTraining(false);
            setMsg('⚠️ Training is still running in background (timeout polling). Check server logs.');
          } else {
            setMsg(`⏳ Training in progress... (${attempts * 3}s elapsed)`);
          }
        } catch { /* ignore poll errors */ }
      }, 3000);
    } catch (e) {
      setMsg(`❌ Training failed: ${e.response?.data?.message ?? e.message}`);
      setTraining(false);
    }
  };

  const handleCfEval = async () => {
    setCfLoading(true); setMsg('');
    try {
      const r = await adminApi.evaluate();
      setCfMetrics(r.data);
      setMsg('✅ CF Evaluation complete!');
    } catch (e) { setMsg(`❌ CF Evaluation failed: ${e.response?.data?.error ?? e.message}`); }
    finally { setCfLoading(false); }
  };

  const handleCbEval = async () => {
    setCbLoading(true); setMsg('');
    try {
      const r = await adminApi.evaluateCb();
      setCbMetrics(r.data);
      setMsg('✅ CB Evaluation complete!');
    } catch (e) { setMsg(`❌ CB Evaluation failed: ${e.response?.data?.error ?? e.message}`); }
    finally { setCbLoading(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this user?')) return;
    await adminApi.deleteUser(id);
    setUsers(u => u.filter(x => x._id !== id));
  };

  return (
    <div className="fade-in">
      <div className="page-header">
        <h1 className="page-title">Admin Dashboard</h1>
        <p className="page-subtitle">System management & model control</p>
      </div>

      {/* Stats */}
      <div className="stats-grid">
        {[
          { icon: '👥', value: stats?.total_users,        label: 'Total Users' },
          { icon: '🎵', value: stats?.total_tracks,       label: 'Total Tracks' },
          { icon: '▶️', value: stats?.total_interactions, label: 'Interactions' },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className="stat-icon">{s.icon}</div>
            <div className="stat-value">
              {s.value !== undefined ? Number(s.value).toLocaleString() : '—'}
            </div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
      </div>

      {msg && (
        <div className={`alert ${msg.startsWith('✅') ? 'alert-success' : 'alert-error'}`}>
          {msg}
        </div>
      )}

      {/* ALS Training */}
      <div className="admin-section">
        <div className="admin-section-title">🤖 Model Training</div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button className="btn btn-primary" onClick={handleTrain} disabled={training}>
            {training ? <><span className="spin">⟳</span> Training ALS…</> : '🚀 Run ALS Training'}
          </button>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Trains Collaborative Filtering model. Required before hybrid recommendations work.
          </span>
        </div>
        <div style={{ marginTop: 8, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          Note: Content-Based model does not need training — it uses pre-computed audio feature vectors stored in MongoDB.
        </div>
      </div>

      {/* Evaluation — CF & CB side by side */}
      <div className="admin-section">
        <div className="admin-section-title">📊 Model Evaluation (80/20 Time-Split)</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <MetricsCard
            modelLabel="Collaborative Filtering (ALS)"
            color="var(--accent)"
            metrics={cfMetrics}
            running={cfLoading}
            onRun={handleCfEval}
            btnLabel="📊 Evaluate CF"
          />
          <MetricsCard
            modelLabel="Content-Based (Cosine Similarity)"
            color="#6c63ff"
            metrics={cbMetrics}
            running={cbLoading}
            onRun={handleCbEval}
            btnLabel="📊 Evaluate CB"
          />
        </div>

        {/* Metrics explanation */}
        <div style={{
          marginTop: 16, padding: '12px 16px',
          background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)',
          fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.7
        }}>
          <strong style={{ color: 'var(--text-primary)' }}>Metrics Explanation</strong><br />
          <b>NDCG@10</b> — Đo thứ tự xếp hạng: bài user thích có được gợi ý lên đầu không?<br />
          <b>Recall@K</b> — Tỷ lệ bài user thực sự nghe xuất hiện trong top K gợi ý.<br />
          <b>Precision@K</b> — Tỷ lệ bài trong top K gợi ý mà user thực sự thích.<br />
          <b>Coverage</b> — % catalog bài hát từng được gợi ý ra (diversity metric).<br />
          Split: <b>80% train / 20% test</b> theo thứ tự thời gian <code>last_played</code>.
        </div>
      </div>

      {/* User Table */}
      <div className="admin-section">
        <div className="admin-section-title">👥 Users ({users.length})</div>
        <div style={{ overflowX: 'auto' }}>
          <table className="user-table">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Genres</th>
                <th>Mood</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u._id}>
                  <td>{u.username}</td>
                  <td><span className={`badge badge-${u.role}`}>{u.role}</span></td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {u.onboarding_preferences?.favorite_genres?.join(', ') ?? '—'}
                  </td>
                  <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                    {u.onboarding_preferences?.mood ?? '—'}
                  </td>
                  <td>
                    {u.role !== 'admin' && (
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(u._id)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
