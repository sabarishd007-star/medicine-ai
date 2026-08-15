import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage, firebaseErrorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ fullName: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    if (form.password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      await register(form);
      navigate('/dashboard');
    } catch (err) {
      setError(firebaseErrorMessage(err, errorMessage(err, 'Could not create the account.')));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container-narrow">
      <div className="card">
        <h2>Create account</h2>
        <p className="muted small">Takes a moment. Your scans stay tied to this account.</p>

        {error && <div className="alert alert-danger">{error}</div>}

        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input
              id="fullName"
              required
              maxLength={120}
              value={form.fullName}
              onChange={(e) => setForm({ ...form, fullName: e.target.value })}
            />
          </div>
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
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
            <span className="tiny muted">Minimum 8 characters.</span>
          </div>
          <button type="submit" className="btn-primary" disabled={busy} style={{ width: '100%' }}>
            {busy ? <span className="spinner" /> : 'Create account'}
          </button>
        </form>

        <p className="small muted" style={{ marginTop: 16, marginBottom: 0 }}>
          Already registered? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
