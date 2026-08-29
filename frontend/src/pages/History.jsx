import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage, scanApi } from '../api/client';

export default function History() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    scanApi
      .history()
      .then((data) => {
        setRows(Array.isArray(data) ? data : []);
      })
      .catch((err) => setError(errorMessage(err, 'Could not load scan history.')))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const remove = async (id) => {
    if (!window.confirm('Delete this scan record?')) {
      return;
    }
    try {
      await scanApi.remove(id);
      setRows((current) => current.filter((row) => row.id !== id));
    } catch (err) {
      setError(errorMessage(err, 'Could not delete the scan.'));
    }
  };

  const safeRows = Array.isArray(rows) ? rows : [];

  return (
    <div className="container">
      <div className="row spread">
        <h1 style={{ marginBottom: 0 }}>Scan history</h1>
        <Link to="/dashboard" className="small">
          New scan &rarr;
        </Link>
      </div>
      <p className="muted">Every screening run tied to your account.</p>

      {error && <div className="alert alert-danger">{error}</div>}

      {loading ? (
        <p className="muted">Loading&hellip;</p>
      ) : safeRows.length === 0 ? (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No scans yet. <Link to="/dashboard">Pick a module</Link> to run your first screening.
          </p>
        </div>
      ) : (
        <div className="card" style={{ padding: 0, overflowX: 'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Module</th>
                <th>Patient</th>
                <th>Finding</th>
                <th>Confidence</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {safeRows.map((row) => (
                <tr key={row.id}>
                  <td className="tiny muted">
                    {row.createdAt ? new Date(row.createdAt).toLocaleString() : 'N/A'}
                  </td>
                  <td className="small">{row.diseaseDisplay || row.disease || 'Module'}</td>
                  <td className="small">
                    {row.patientName || 'Unknown'}
                    {row.patientAge ? <span className="muted"> ({row.patientAge})</span> : ''}
                  </td>
                  <td className="small">
                    {row.prediction || 'N/A'}
                    <div>
                      {row.modelStatus === 'UNTRAINED_BACKBONE' ? (
                        <span className="badge badge-warn">Not valid</span>
                      ) : row.conclusive ? (
                        <span className="badge badge-ok">Conclusive</span>
                      ) : (
                        <span className="badge badge-danger">Inconclusive</span>
                      )}
                    </div>
                  </td>
                  <td className="small">
                    {typeof row.confidence === 'number' ? `${row.confidence.toFixed(1)}%` : 'N/A'}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <Link to={`/result/${row.id}`} className="small">
                      View
                    </Link>
                    <button
                      type="button"
                      className="btn-danger"
                      onClick={() => remove(row.id)}
                      style={{ marginLeft: 10, padding: '4px 10px', fontSize: 12 }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
