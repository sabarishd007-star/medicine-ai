import { Component } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import { AuthProvider, useAuth } from './context/AuthContext';
import Assistant from './pages/Assistant';
import Dashboard from './pages/Dashboard';
import DiseaseDetail from './pages/DiseaseDetail';
import EmergencyNetwork from './pages/EmergencyNetwork';
import History from './pages/History';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Result from './pages/Result';

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('UI Runtime Error caught by ErrorBoundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="container" style={{ paddingTop: 40, maxWidth: 640 }}>
          <div className="card" style={{ borderTop: '4px solid var(--danger, #dc2626)' }}>
            <h2 style={{ marginTop: 0 }}>Something went wrong</h2>
            <p className="muted small">
              An unexpected error occurred while rendering this page.
            </p>
            <div className="alert alert-danger tiny" style={{ margin: '16px 0' }}>
              {this.state.error?.message || 'Unknown render error'}
            </div>
            <div className="row" style={{ gap: 10 }}>
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.reload();
                }}
              >
                Reload Page
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  this.setState({ hasError: false, error: null });
                  window.location.href = '/dashboard';
                }}
              >
                Go to Dashboard
              </button>
            </div>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="container" style={{ paddingTop: 40 }}>
        <p className="muted">Loading account session&hellip;</p>
      </div>
    );
  }
  return user ? children : <Navigate to="/login" replace />;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="container" style={{ paddingTop: 40 }}>
        <p className="muted">Loading&hellip;</p>
      </div>
    );
  }
  return user ? <Navigate to="/dashboard" replace /> : children;
}

function AppRoutes() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route
          path="/login"
          element={
            <PublicOnly>
              <Login />
            </PublicOnly>
          }
        />
        <Route
          path="/register"
          element={
            <PublicOnly>
              <Register />
            </PublicOnly>
          }
        />
        <Route
          path="/dashboard"
          element={
            <Protected>
              <Dashboard />
            </Protected>
          }
        />
        <Route
          path="/disease/:key"
          element={
            <Protected>
              <DiseaseDetail />
            </Protected>
          }
        />
        <Route
          path="/result/:id"
          element={
            <Protected>
              <Result />
            </Protected>
          }
        />
        {/* Public on purpose: an emergency lookup must not require a login. */}
        <Route path="/emergency" element={<EmergencyNetwork />} />
        <Route
          path="/assistant"
          element={
            <Protected>
              <Assistant />
            </Protected>
          }
        />
        <Route
          path="/history"
          element={
            <Protected>
              <History />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
