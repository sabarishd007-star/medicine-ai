import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { errorMessage, scanApi } from '../api/client';
import { Disclaimer } from '../components/Layout';

export default function Result() {
  const { id } = useParams();
  const location = useLocation();
  const passed = location.state?.analysis?.result;

  const [result] = useState(passed ?? null);
  const [summary, setSummary] = useState(null);
  const [heatmap, setHeatmap] = useState(null);
  const [error, setError] = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (result) {
      return;
    }
    // Direct navigation or refresh: fall back to the stored summary.
    scanApi
      .history()
      .then((rows) => {
        const match = rows.find((row) => String(row.id) === String(id));
        if (match) {
          setSummary(match);
        } else {
          setError('Scan not found.');
        }
      })
      .catch((err) => setError(errorMessage(err)));
  }, [id, result]);

  useEffect(() => {
    let revoked = null;
    scanApi
      .fetchHeatmapBlob(id)
      .then((url) => {
        revoked = url;
        setHeatmap(url);
      })
      .catch(() => setHeatmap(null));
    return () => {
      if (revoked) {
        URL.revokeObjectURL(revoked);
      }
    };
  }, [id]);

  const download = async () => {
    setDownloading(true);
    try {
      await scanApi.downloadReport(id);
    } catch (err) {
      setError(errorMessage(err, 'Could not download the report.'));
    } finally {
      setDownloading(false);
    }
  };

  const view = result ?? summary;
  if (error && !view) {
    return (
      <div className="container">
        <div className="alert alert-danger">{error}</div>
        <Link to="/history">Back to history</Link>
      </div>
    );
  }
  if (!view) {
    return (
      <div className="container">
        <p className="muted">Loading result&hellip;</p>
      </div>
    );
  }

  const prediction = view.prediction;
  const confidence = view.confidence;
  const conclusive = result ? result.is_conclusive : summary?.conclusive;
  const untrained = (result?.model_status ?? summary?.modelStatus) === 'UNTRAINED_BACKBONE';
  const probabilities = result?.class_probabilities;
  const guidance = result?.guidance;

  const tone = untrained ? 'var(--warn)' : conclusive ? 'var(--ok)' : 'var(--danger)';

  return (
    <div className="container">
      <Link to="/history" className="small">
        &larr; Scan history
      </Link>

      <h1 style={{ marginTop: 12 }}>Screening result</h1>
      <p className="muted">
        {result?.disease_display ?? summary?.diseaseDisplay ?? summary?.disease} &middot;{' '}
        {result?.patient?.name ?? summary?.patientName}, age{' '}
        {result?.patient?.age ?? summary?.patientAge}
      </p>

      {error && <div className="alert alert-danger">{error}</div>}

      {untrained && (
        <div className="alert alert-warn">
          <strong>Not clinically valid.</strong>{' '}
          {result?.notice ??
            'This module has no trained checkpoint, so the figures below carry no clinical meaning.'}
        </div>
      )}

      {result?.safety_warning && (
        <div className="alert alert-danger">{result.safety_warning}</div>
      )}

      <div className="grid grid-2" style={{ alignItems: 'start' }}>
        <div className="card">
          <h3>Finding</h3>
          <p style={{ fontSize: 22, fontWeight: 700, color: tone, margin: '4px 0 10px' }}>
            {prediction}
          </p>

          <div className="tiny muted">Confidence</div>
          <div className="row" style={{ gap: 10, marginBottom: 12 }}>
            <div className="bar" style={{ flex: 1 }}>
              <span style={{ width: `${Math.min(confidence ?? 0, 100)}%`, background: tone }} />
            </div>
            <strong>{confidence?.toFixed(2)}%</strong>
          </div>

          {!conclusive && !untrained && (
            <div className="alert alert-warn tiny">
              Below the {result?.confidence_threshold ?? 75}% confidence gate, so no class is
              asserted. Treat this as inconclusive.
            </div>
          )}

          {(result?.stage ?? summary?.stage) && (
            <p className="small">
              <strong>Indicated stage:</strong> {result?.stage ?? summary?.stage}
            </p>
          )}

          {probabilities && (
            <>
              <h3 style={{ marginTop: 18 }}>Class probabilities</h3>
              <table>
                <tbody>
                  {Object.entries(probabilities).map(([label, value]) => (
                    <tr key={label}>
                      <td>{label}</td>
                      <td style={{ width: 130 }}>
                        <div className="bar">
                          <span style={{ width: `${Math.min(value, 100)}%` }} />
                        </div>
                      </td>
                      <td style={{ width: 62, textAlign: 'right' }}>{value}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result?.score_semantics === 'ordinal_sigmoid' && (
                <p className="tiny muted" style={{ marginTop: 8 }}>
                  These are per-level sigmoid scores from an ordinal head, not a softmax
                  distribution, so they do not sum to 100%.
                </p>
              )}
            </>
          )}

          <button
            type="button"
            className="btn-primary"
            onClick={download}
            disabled={downloading}
            style={{ width: '100%', marginTop: 18 }}
          >
            {downloading ? <span className="spinner" /> : 'Download PDF report'}
          </button>
        </div>

        <div>
          <div className="card">
            <h3>Grad-CAM explanation</h3>
            {heatmap ? (
              <>
                <img
                  src={heatmap}
                  alt="Grad-CAM activation overlay"
                  style={{
                    width: '100%',
                    borderRadius: 8,
                    border: '1px solid var(--border)',
                  }}
                />
                <p className="tiny muted" style={{ marginTop: 8, marginBottom: 0 }}>
                  Warm regions drove the prediction.
                  {result?.gradcam_coverage != null && (
                    <> Activation coverage {(result.gradcam_coverage * 100).toFixed(1)}%.</>
                  )}
                </p>
              </>
            ) : (
              <p className="small muted" style={{ margin: 0 }}>
                No heatmap available for this scan.
              </p>
            )}
          </div>

          {guidance && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3>Guidance</h3>
              {guidance.summary && (
                <p className="small">
                  <strong>Summary.</strong> {guidance.summary}
                </p>
              )}
              {guidance.stage_info && guidance.stage_info !== 'N/A' && (
                <p className="small">
                  <strong>Stage context.</strong> {guidance.stage_info}
                </p>
              )}
              {guidance.next_steps && (
                <p className="small" style={{ marginBottom: 0 }}>
                  <strong>Next steps.</strong> {guidance.next_steps}
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      <Disclaimer />
    </div>
  );
}
