import { NavLink } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

const HomeIcon  = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>;
const SearchIcon= () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27A6.5 6.5 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>;
const ProfileIcon=()=><svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/></svg>;
const AdminIcon = () => <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2L3 7v5c0 5.25 3.75 10.2 9 11.4C17.25 22.2 21 17.25 21 12V7l-9-5zm-2 14l-4-4 1.41-1.41L10 13.17l6.59-6.59L18 8l-8 8z"/></svg>;
const NoteIcon  = () => <svg width="24" height="24" fill="currentColor" viewBox="0 0 24 24"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>;

export default function Sidebar() {
  const { user, logout } = useAuth();
  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <NoteIcon />
        MusicRec
      </div>
      <NavLink to="/"       end className={({isActive})=>`nav-link${isActive?' active':''}`}><HomeIcon />Home</NavLink>
      <NavLink to="/search"     className={({isActive})=>`nav-link${isActive?' active':''}`}><SearchIcon />Search</NavLink>
      <NavLink to="/profile"    className={({isActive})=>`nav-link${isActive?' active':''}`}><ProfileIcon />Profile</NavLink>
      {user?.role === 'admin' && (
        <NavLink to="/admin"    className={({isActive})=>`nav-link${isActive?' active':''}`}><AdminIcon />Admin</NavLink>
      )}
      <div className="sidebar-divider" />
      <div style={{padding:'8px 12px',fontSize:'0.8rem',color:'var(--text-muted)'}}>
        Signed in as <strong style={{color:'var(--text-secondary)'}}>{user?.username}</strong>
      </div>
      <button className="nav-link" style={{marginTop:'auto'}} onClick={logout}>
        <svg width="20" height="20" fill="currentColor" viewBox="0 0 24 24"><path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.58L17 17l5-5-5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/></svg>
        Logout
      </button>
    </nav>
  );
}
