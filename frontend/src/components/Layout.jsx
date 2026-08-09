import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function Disclaimer() {
  return (
    <div className="alert alert-warn" style={{ marginTop: 28 }}>
      <strong>Screening aid, not a diagnosis.</strong> MediScan AI provides an AI-assisted
      estimate from image pattern recognition. It is not a certified diagnostic device and does
      not replace evaluation by a licensed medical professional.
    </div>
  );
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const linkStyle = ({ isActive }) => ({
    color: isActive ? 'var(--brand)' : 'var(--muted)',
    fontWeight: isActive ? 700 : 500,
    fontSize: 14,
    textDecoration: 'none',
  });

  return (
    <>
      <header
        style={{
          background: '#fff',
          borderBottom: '1px solid var(--border)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          className="container row spread"
          style={{ paddingTop: 12, paddingBottom: 12, maxWidth: 1080 }}
        >
          <Link to={user ? '/dashboard' : '/'} style={{ textDecoration: 'none' }}>
            <span style={{ fontWeight: 800, fontSize: 18, color: 'var(--ink)' }}>
              MediScan<span style={{ color: 'var(--brand)' }}>AI</span>
            </span>
          </Link>

          <nav className="row" style={{ gap: 18 }}>
            {user ? (
              <>
                <NavLink to="/dashboard" style={linkStyle}>
                  Dashboard
                </NavLink>
                <NavLink to="/emergency" style={linkStyle}>
                  Emergency
                </NavLink>
                <NavLink to="/assistant" style={linkStyle}>
                  Assistant
                </NavLink>
                <NavLink to="/history" style={linkStyle}>
                  History
                </NavLink>
                <span className="small muted">{user.fullName}</span>
                <button type="button" className="btn-ghost" onClick={handleLogout}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/emergency" style={linkStyle}>
                  Emergency
                </NavLink>
                <NavLink to="/login" style={linkStyle}>
                  Log in
                </NavLink>
                <Link to="/register">
                  <button type="button" className="btn-primary">
                    Get started
                  </button>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main>{children}</main>
    </>
  );
}
