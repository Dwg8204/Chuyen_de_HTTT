import { usePlayer } from '../../contexts/PlayerContext';

const PlayIcon  = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>;
const PauseIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>;
const NoteIcon  = () => <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>;

export default function MusicPlayer() {
  const { currentTrack, isPlaying, previewUrl, progress, togglePlay, seekTo } = usePlayer();

  const handleProgressClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    seekTo(pct);
  };

  return (
    <div className="player-bar">
      {/* Track Info */}
      <div className="player-track-info">
        <div className="player-artwork">
          {currentTrack ? <NoteIcon /> : null}
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="player-track-name">
            {currentTrack?.title ?? 'No track selected'}
          </div>
          <div className="player-track-artist">
            {currentTrack?.artist ?? ''}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="player-controls">
        <div className="player-btns">
          <button className="player-btn play-pause" onClick={togglePlay} disabled={!currentTrack}>
            {isPlaying ? <PauseIcon /> : <PlayIcon />}
          </button>
        </div>
        <div className="player-progress">
          <span className="progress-time">0:00</span>
          <div className="progress-bar" onClick={handleProgressClick}>
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-time">0:30</span>
        </div>
        {currentTrack && !previewUrl && (
          <div className="player-no-preview">No preview available for this track</div>
        )}
      </div>

      {/* Right side placeholder */}
      <div />
    </div>
  );
}
