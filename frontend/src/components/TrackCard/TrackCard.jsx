import { usePlayer } from '../../contexts/PlayerContext';

const PlayIcon = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>;
const NoteEmoji = ({ genre }) => {
  const map = { rock:'🎸', jazz:'🎷', hiphop:'🎤', electronic:'🎛️', acoustic:'🪕', indie:'🎵', rnb:'🎶', pop:'⭐' };
  return map[genre?.[0]] ?? '🎵';
};

export default function TrackCard({ track }) {
  const { playTrack, currentTrack, isPlaying } = usePlayer();
  const isActive = currentTrack?._id === track._id;

  return (
    <div
      className={`track-card${isActive ? ' playing' : ''}`}
      onClick={() => playTrack(track)}
    >
      <div className="track-artwork">
        <NoteEmoji genre={track.genre} />
        <div className="track-play-overlay">
          <div className="play-btn-overlay">
            {isActive && isPlaying
              ? <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
              : <PlayIcon />
            }
          </div>
        </div>
      </div>
      <div className="track-title">{track.title}</div>
      <div className="track-artist">{track.artist}</div>
      {track.genre?.length > 0 && (
        <div className="track-genres">
          {track.genre.slice(0, 2).map((g) => (
            <span key={g} className="genre-tag">{g}</span>
          ))}
        </div>
      )}
    </div>
  );
}
