import { useEffect, useRef } from 'react';
import { usePlayer } from '../../contexts/PlayerContext';
import './SimilarPopup.css';

const PlayIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
    <path d="M8 5v14l11-7z"/>
  </svg>
);

export default function SimilarPopup({ tracks, onClose, sourceTrack }) {
  const { playTrack, currentTrack } = usePlayer();
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose(); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (!tracks || tracks.length === 0) return null;

  return (
    <div className="similar-popup" ref={ref}>
      <div className="similar-popup-header">
        <div className="similar-popup-title">Có thể bạn thích</div>
        <button className="similar-popup-close" onClick={onClose}>✕</button>
      </div>
      <div className="similar-popup-source">
        Dựa trên: <em>{sourceTrack?.title ?? 'bài vừa nghe'}</em>
      </div>
      <div className="similar-popup-list">
        {tracks.map((t, i) => {
          if (!t) return null;
          const isActive = currentTrack?._id === t._id;
          return (
            <div
              key={t._id ?? i}
              className={`similar-item${isActive ? ' playing' : ''}`}
              onClick={() => playTrack(t)}
            >
              <div className="similar-item-artwork">
                <span className="similar-item-num">{i + 1}</span>
                <span className="similar-item-play"><PlayIcon /></span>
              </div>
              <div className="similar-item-info">
                <div className="similar-item-title">{t.title}</div>
                <div className="similar-item-artist">{t.artist}</div>
              </div>
              {isActive && <div className="similar-item-equalizer">▶</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
