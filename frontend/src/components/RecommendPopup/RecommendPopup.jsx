import { usePlayer } from '../../contexts/PlayerContext';

const NoteIcon = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>;

export default function RecommendPopup() {
  const { currentTrack, similarTracks, setShowPopup, playTrack } = usePlayer();

  if (!currentTrack || similarTracks.length === 0) return null;

  return (
    <div className="rec-popup fade-in">
      <div className="rec-popup-header">
        <h4>🎵 Because you played "{currentTrack.title}"</h4>
        <button className="popup-close" onClick={() => setShowPopup(false)}>✕</button>
      </div>

      {similarTracks.map((track) => (
        <div key={track._id} className="popup-track" onClick={() => playTrack(track)}>
          <div className="popup-artwork"><NoteIcon /></div>
          <div className="popup-info">
            <div className="popup-title">{track.title}</div>
            <div className="popup-artist">{track.artist}</div>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="var(--accent)"><path d="M8 5v14l11-7z"/></svg>
        </div>
      ))}
    </div>
  );
}
