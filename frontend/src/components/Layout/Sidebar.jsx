import { NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const HomeIcon    = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>;
const SearchIcon  = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.5 6.5 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>;
const ProfileIcon = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg>;
const AdminIcon   = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L3 7v5c0 5.25 3.75 10.2 9 11.4C17.25 22.2 21 17.25 21 12V7l-9-5zm-2 14l-4-4 1.41-1.41L10 13.17l6.59-6.59L18 8l-8 8z"/></svg>;
const CollabIcon  = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>;
const ContentIcon = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>;

const SpotifyLogo = () => (
  <svg width="26" height="26" viewBox="0 0 168 168" fill="#1DB954">
    <path d="M84 0C37.6 0 0 37.6 0 84s37.6 84 84 84 84-37.6 84-84S130.4 0 84 0zm38.6 121.2c-1.5 2.4-4.7 3.2-7.1 1.7-19.5-11.9-44-14.6-72.9-8-2.8.6-5.5-1.1-6.1-3.9-.6-2.8 1.1-5.5 3.9-6.1 31.6-7.2 58.7-4.1 80.6 9.2 2.4 1.5 3.2 4.7 1.6 7.1zm10.3-22.9c-1.9 3-5.8 4-8.9 2.1-22.3-13.7-56.3-17.7-82.7-9.7-3.4 1-7-.9-8-4.3-1-3.4.9-7 4.3-8 30.1-9.1 67.5-4.7 93.1 11.1 3 1.9 4 5.9 2.2 8.8zm.9-23.8c-26.7-15.9-70.8-17.3-96.3-9.6-4.1 1.2-8.4-1.1-9.6-5.2-1.2-4.1 1.1-8.4 5.2-9.6 29.3-8.9 78-7.2 108.7 11.1 3.7 2.2 4.9 7 2.7 10.7-2.2 3.7-7 4.9-10.7 2.6z"/>
  </svg>
);

const navLinkClass = ({ isActive }) =>
  `nav-link${isActive ? ' active' : ''}`;

export default function Sidebar() {
  const { user, logout } = useAuth();
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <SpotifyLogo />
        <span>MusicRec</span>
      </div>

      <div className="sidebar-section-label">Main</div>
      <NavLink to="/"       end className={navLinkClass}><HomeIcon />Home</NavLink>
      <NavLink to="/search"     className={navLinkClass}><SearchIcon />Search</NavLink>

      <div className="sidebar-section-label">Discover</div>
      <NavLink to="/collab"     className={navLinkClass}><CollabIcon />Collab Picks</NavLink>
      <NavLink to="/content"    className={navLinkClass}><ContentIcon />Taste Match</NavLink>

      <div className="sidebar-section-label">Account</div>
      <NavLink to="/profile"    className={navLinkClass}><ProfileIcon />Profile</NavLink>
      {user?.role === 'admin' && (
        <NavLink to="/admin"    className={navLinkClass}><AdminIcon />Admin</NavLink>
      )}

      <div className="sidebar-divider" />
      <div className="sidebar-user">
        <div className="sidebar-avatar">{user?.username?.[0]?.toUpperCase()}</div>
        <span>{user?.username}</span>
      </div>
      <button className="nav-link sidebar-logout" onClick={logout}>
        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5-5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>
        Logout
      </button>
    </nav>
  );
}
