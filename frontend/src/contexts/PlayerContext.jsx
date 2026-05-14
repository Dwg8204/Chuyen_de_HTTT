import { createContext, useContext, useState, useRef, useCallback } from 'react';
import { tracksApi, playApi, recApi } from '../services/api';

const PlayerContext = createContext(null);

export function PlayerProvider({ children }) {
  const [currentTrack, setCurrentTrack]   = useState(null);
  const [isPlaying, setIsPlaying]         = useState(false);
  const [previewUrl, setPreviewUrl]       = useState(null);
  const [similarTracks, setSimilarTracks] = useState([]);
  const [showPopup, setShowPopup]         = useState(false);
  const [progress, setProgress]           = useState(0);
  const audioRef = useRef(new Audio());

  const playTrack = useCallback(async (track) => {
    // Stop current
    audioRef.current.pause();
    setIsPlaying(false);
    setCurrentTrack(track);
    setSimilarTracks([]);

    // Record play (fire & forget)
    playApi.record(track._id).catch(() => {});

    // Fetch iTunes preview
    try {
      const res = await tracksApi.itunesPreview(track._id);
      const url = res.data?.previewUrl;
      if (url) {
        audioRef.current.src = url;
        audioRef.current.play();
        setIsPlaying(true);
        setPreviewUrl(url);
      } else {
        setPreviewUrl(null);
        setIsPlaying(false);
      }
    } catch {
      setPreviewUrl(null);
    }

    // Fetch similar tracks for popup
    try {
      const simRes = await recApi.similar(track._id);
      setSimilarTracks(simRes.data || []);
      setShowPopup(true);
    } catch { setSimilarTracks([]); }
  }, []);

  const togglePlay = useCallback(() => {
    if (!previewUrl) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  }, [isPlaying, previewUrl]);

  // Track audio progress
  audioRef.current.ontimeupdate = () => {
    const dur = audioRef.current.duration;
    if (dur) setProgress((audioRef.current.currentTime / dur) * 100);
  };
  audioRef.current.onended = () => { setIsPlaying(false); setProgress(0); };

  const seekTo = useCallback((pct) => {
    const dur = audioRef.current.duration;
    if (dur) audioRef.current.currentTime = (pct / 100) * dur;
  }, []);

  return (
    <PlayerContext.Provider value={{
      currentTrack, isPlaying, previewUrl, similarTracks,
      showPopup, setShowPopup, progress,
      playTrack, togglePlay, seekTo,
    }}>
      {children}
    </PlayerContext.Provider>
  );
}

export const usePlayer = () => useContext(PlayerContext);
