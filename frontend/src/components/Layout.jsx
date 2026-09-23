import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function Disclaimer() {
  return (
    <div
      className="alert alert-warn"
      style={{ marginTop: 32, display: 'flex', gap: 10, alignItems: 'flex-start' }}
    >
      <span style={{ fontSize: 16 }}>⚕️</span>
      <div>
        <strong>Screening aid, not a diagnosis.</strong> MediScan AI provides AI-assisted
        estimates from image pattern recognition and clinical variable analysis. It is not a
        certified diagnostic device and does not replace evaluation by a licensed medical
        professional. Always consult a qualified clinician before making any medical decision.
      </div>
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
    padding: '4px 0',
    position: 'relative',
    transition: 'color 0.15s ease',
    borderBottom: isActive ? '2px solid var(--brand)' : '2px solid transparent',
    paddingBottom: 2,
  });

  return (
    <>
      <header
        style={{
          background: 'rgba(6, 11, 23, 0.88)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid var(--border)',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}
      >
        <div
          className="container row spread"
          style={{ paddingTop: 14, paddingBottom: 14, maxWidth: 1100 }}
        >
          {/* Logo */}
          <Link to={user ? '/dashboard' : '/'} style={{ textDecoration: 'none' }}>
            <span
              style={{
                fontWeight: 900,
                fontSize: 20,
                letterSpacing: '-0.04em',
                color: 'var(--ink)',
              }}
            >
              Medi
              <span
                style={{
                  background: 'linear-gradient(135deg, var(--brand), var(--neon-teal))',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                  backgroundClip: 'text',
                }}
              >
                Scan AI
              </span>
            </span>
          </Link>

          {/* Nav links */}
          <nav className="row" style={{ gap: 20 }}>
            {user ? (
              <>
                <NavLink to="/dashboard" style={linkStyle}>Dashboard</NavLink>
                <NavLink to="/heart-risk" style={linkStyle}>Heart Risk</NavLink>
                <NavLink to="/emergency" style={linkStyle}>Emergency</NavLink>
                <NavLink to="/assistant" style={linkStyle}>Assistant</NavLink>
                <NavLink to="/history" style={linkStyle}>History</NavLink>
                <span
                  style={{
                    fontSize: 13,
                    color: 'var(--muted)',
                    borderLeft: '1px solid var(--border)',
                    paddingLeft: 16,
                    maxWidth: 140,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {user.fullName}
                </span>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={handleLogout}
                  style={{ padding: '7px 14px', fontSize: 13 }}
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                <NavLink to="/emergency" style={linkStyle}>Emergency</NavLink>
                <NavLink to="/login" style={linkStyle}>Log in</NavLink>
                <Link to="/register">
                  <button type="button" className="btn-primary" style={{ padding: '8px 18px', fontSize: 13 }}>
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
