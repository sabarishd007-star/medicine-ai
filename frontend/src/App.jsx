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

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="container">
        <p className="muted">Loading&hellip;</p>
      </div>
    );
  }
  return user ? children : <Navigate to="/login" replace />;
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return null;
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
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
