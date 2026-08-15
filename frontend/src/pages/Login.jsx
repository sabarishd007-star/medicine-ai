import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage, firebaseErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(form.email, form.password);
      navigate('/dashboard');
    } catch (err) {
      setError(firebaseErrorMessage(err, errorMessage(err, 'Could not sign in.')));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-narrow">
      <div className="card">
        <h2>Log in</h2>
        <p className="muted small">Access your dashboard and scan history.</p>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </div>
          <button type="submit" className="btn-primary" disabled={busy} style={{ width: '100%' }}>
            {busy ? <span className="spinner" /> : 'Log in'}
          </button>
        </form>

        <p className="small muted" style={{ marginTop: 16, marginBottom: 0 }}>
          No account? <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  );
}
