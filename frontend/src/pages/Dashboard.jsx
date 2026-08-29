import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage, scanApi } from '../api/client';
import { Disclaimer } from '../components/Layout';
import { useAuth } from '../context/AuthContext';

export function ModelBadge({ status }) {
  if (status === 'TRAINED') {
    return <span className="badge badge-ok">Trained</span>;
  }
  return <span className="badge badge-warn">Not trained</span>;
}

/**
 * Accuracy alone is misleading when one class dominates, so the card always
 * shows the always-guess-commonest baseline next to it, and surfaces
 * sensitivity when the module has a measured false-negative rate.
 */
function MetricsLine({ metrics }) {
  if (!metrics || metrics.accuracy == null) {
    return <p className="tiny muted" style={{ margin: '8px 0 0' }}>Accuracy not measured.</p>;
  }
  const safety = metrics.safety;
  const weak =
    metrics.majority_class_baseline != null &&
    metrics.accuracy - metrics.majority_class_baseline < 0.05;

  return (
    <div style={{ marginTop: 10 }}>
      <div className="tiny muted">
        Accuracy <strong style={{ color: 'var(--ink)' }}>
          {(metrics.accuracy * 100).toFixed(1)}%
        </strong>
        {metrics.majority_class_baseline != null && (
          <> &middot; baseline {(metrics.majority_class_baseline * 100).toFixed(1)}%</>
        )}
        {metrics.dataset?.samples_evaluated && (
          <> &middot; n={metrics.dataset.samples_evaluated}</>
        )}
      </div>
      {safety && (
        <div
          className="tiny"
          style={{ marginTop: 4, color: safety.sensitivity_recall < 0.7 ? 'var(--danger)' : 'var(--muted)' }}
        >
          Sensitivity {(safety.sensitivity_recall * 100).toFixed(0)}% &mdash; misses{' '}
          {safety.missed_diseased_cases}/{safety.diseased_samples} diseased cases
        </div>
      )}
      {weak && (
        <div className="tiny" style={{ color: 'var(--danger)', marginTop: 4 }}>
          Barely above guessing the commonest class.
        </div>
      )}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [diseases, setDiseases] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [usingFallback, setUsingFallback] = useState(false);

  const loadDiseases = () => {
    setLoading(true);
    setError('');
    scanApi
      .diseases()
      .then((list) => {
        setDiseases(Array.isArray(list) ? list : []);
        setUsingFallback(false);
      })
      .catch(() => {
        setUsingFallback(true);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDiseases();
  }, []);

  return (
    <div className="container">
      <div className="row spread" style={{ marginBottom: 4 }}>
        <h1 style={{ marginBottom: 0 }}>Dashboard</h1>
        <Link to="/history" className="small">
          View scan history &rarr;
        </Link>
      </div>
      <p className="muted">
        {user?.fullName && <>{user.fullName} &middot; </>}
        {user?.scanCount ?? 0} scan{user?.scanCount === 1 ? '' : 's'} run
      </p>

      {usingFallback && (
        <div className="alert alert-warn">
          <strong>ML service offline.</strong> Showing catalogue from local registry.
          Scanning requires the inference service:{' '}
          <code>uvicorn app:app --port 8001</code>
          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              className="btn-ghost"
              style={{ padding: '4px 12px', fontSize: 13 }}
              onClick={loadDiseases}
            >
              Retry connection
            </button>
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-danger">
          {error}
          <div className="tiny" style={{ marginTop: 6 }}>
            Start the inference service: <code>uvicorn app:app --port 8001</code>
          </div>
        </div>
      )}

      <h2 style={{ marginTop: 28 }}>Screening modules</h2>
      {loading ? (
        <p className="muted">Loading modules&hellip;</p>
      ) : diseases.length === 0 ? (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No screening modules found.{' '}
            <button
              type="button"
              className="btn-ghost"
              style={{ padding: '4px 10px', fontSize: 13 }}
              onClick={loadDiseases}
            >
              Retry
            </button>
          </p>
        </div>
      ) : (
        <div className="grid grid-3">
          {diseases.map((disease) => (
            <div className="card" key={disease.key}>
              <div className="row spread" style={{ alignItems: 'flex-start' }}>
                <h3 style={{ marginBottom: 4 }}>{disease.display_name}</h3>
                <ModelBadge status={disease.model_status} />
              </div>
              <p className="tiny muted" style={{ marginBottom: 6 }}>
                {disease.modality} &middot; {(disease.classes || []).length} classes
              </p>
              <MetricsLine metrics={disease.metrics} />
              <div style={{ marginTop: 14 }}>
                <Link to={`/disease/${disease.key}`}>
                  <button type="button" className="btn-ghost" style={{ width: '100%' }}>
                    Open module
                  </button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}

      <Disclaimer />
    </div>
  );
}
