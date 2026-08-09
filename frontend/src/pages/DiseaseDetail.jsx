import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { errorMessage, scanApi } from '../api/client';
import { ModelBadge } from './Dashboard';

export default function DiseaseDetail() {
  const { key } = useParams();
  const navigate = useNavigate();

  const [diseases, setDiseases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);

  const [form, setForm] = useState({ patientName: '', patientAge: '', patientNotes: '' });
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);

  const disease = useMemo(() => diseases.find((d) => d.key === key), [diseases, key]);

  useEffect(() => {
    scanApi
      .diseases()
      .then(setDiseases)
      .catch((err) => setError(errorMessage(err, 'Could not load module details.')))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const submit = async (event) => {
    event.preventDefault();
    setError('');

    if (!file) {
      setError('Select a scan image to analyse.');
      return;
    }
    const age = Number(form.patientAge);
    if (!Number.isInteger(age) || age < 1 || age > 129) {
      setError('Enter a patient age between 1 and 129.');
      return;
    }

    const payload = new FormData();
    payload.append('disease', key);
    payload.append('patientName', form.patientName.trim());
    payload.append('patientAge', String(age));
    if (form.patientNotes.trim()) {
      payload.append('patientNotes', form.patientNotes.trim());
    }
    payload.append('file', file);

    setSubmitting(true);
    setProgress(0);
    try {
      const data = await scanApi.analyze(payload, (event_) => {
        if (event_.total) {
          setProgress(Math.round((event_.loaded / event_.total) * 100));
        }
      });
      navigate(`/result/${data.scanId}`, { state: { analysis: data } });
    } catch (err) {
      setError(errorMessage(err, 'Analysis failed.'));
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="container">
        <p className="muted">Loading&hellip;</p>
      </div>
    );
  }

  if (!disease) {
    return (
      <div className="container">
        <div className="alert alert-danger">
          Unknown module &ldquo;{key}&rdquo;. <Link to="/dashboard">Back to dashboard</Link>
        </div>
      </div>
    );
  }

  const metrics = disease.metrics;
  const untrained = disease.model_status !== 'TRAINED';

  return (
    <div className="container">
      <Link to="/dashboard" className="small">
        &larr; Dashboard
      </Link>

      <div className="row spread" style={{ marginTop: 12 }}>
        <h1 style={{ marginBottom: 0 }}>{disease.display_name}</h1>
        <ModelBadge status={disease.model_status} />
      </div>
      <p className="muted">
        {disease.modality} &middot; {disease.framework} / {disease.architecture}
      </p>

      {untrained && (
        <div className="alert alert-warn">
          <strong>No trained checkpoint installed.</strong> This module runs an untrained
          classification head. It will return a real number, but that number has no clinical
          meaning and the result is always marked not valid.
        </div>
      )}

      {disease.provenance && (
        <div className="alert alert-info tiny">{disease.provenance}</div>
      )}

      <div className="grid grid-2" style={{ marginTop: 20, alignItems: 'start' }}>
        <div className="card">
          <h3>Patient details &amp; scan</h3>
          {error && <div className="alert alert-danger">{error}</div>}

          <form onSubmit={submit}>
            <div className="field">
              <label htmlFor="patientName">Patient name</label>
              <input
                id="patientName"
                required
                maxLength={160}
                value={form.patientName}
                onChange={(e) => setForm({ ...form, patientName: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="patientAge">Age</label>
              <input
                id="patientAge"
                type="number"
                min={1}
                max={129}
                required
                value={form.patientAge}
                onChange={(e) => setForm({ ...form, patientAge: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="patientNotes">Symptoms / history (optional)</label>
              <textarea
                id="patientNotes"
                rows={3}
                maxLength={1000}
                value={form.patientNotes}
                onChange={(e) => setForm({ ...form, patientNotes: e.target.value })}
              />
            </div>
            <div className="field">
              <label htmlFor="file">{disease.modality} image (JPG / PNG, max 15MB)</label>
              <input
                id="file"
                type="file"
                accept="image/*"
                required
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>

            {preview && (
              <img
                src={preview}
                alt="Selected scan preview"
                style={{
                  width: '100%',
                  maxHeight: 220,
                  objectFit: 'contain',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  marginBottom: 14,
                  background: '#0b0f16',
                }}
              />
            )}

            {submitting && progress > 0 && (
              <div className="bar" style={{ marginBottom: 12 }}>
                <span style={{ width: `${progress}%` }} />
              </div>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={submitting}
              style={{ width: '100%' }}
            >
              {submitting ? <span className="spinner" /> : 'Analyse scan'}
            </button>
          </form>
        </div>

        <div>
          <div className="card">
            <h3>What this module reports</h3>
            <ul className="small muted" style={{ paddingLeft: 18, margin: 0 }}>
              {disease.classes.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
            <p className="tiny muted" style={{ marginTop: 12, marginBottom: 0 }}>
              Predictions below {disease.confidence_threshold}% confidence are returned as
              inconclusive rather than forced into one of these classes.
            </p>
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <h3>Measured performance</h3>
            {metrics?.accuracy != null ? (
              <>
                <table>
                  <tbody>
                    <tr>
                      <td>Accuracy</td>
                      <td>
                        <strong>{(metrics.accuracy * 100).toFixed(1)}%</strong>
                      </td>
                    </tr>
                    <tr>
                      <td>Always-guess baseline</td>
                      <td>{(metrics.majority_class_baseline * 100).toFixed(1)}%</td>
                    </tr>
                    <tr>
                      <td>Macro F1</td>
                      <td>{metrics.macro_f1?.toFixed(3)}</td>
                    </tr>
                    {metrics.safety && (
                      <tr>
                        <td>Sensitivity</td>
                        <td
                          style={{
                            color:
                              metrics.safety.sensitivity_recall < 0.7
                                ? 'var(--danger)'
                                : 'inherit',
                            fontWeight: 700,
                          }}
                        >
                          {(metrics.safety.sensitivity_recall * 100).toFixed(1)}%
                        </td>
                      </tr>
                    )}
                    <tr>
                      <td>Samples</td>
                      <td>{metrics.dataset?.samples_evaluated}</td>
                    </tr>
                  </tbody>
                </table>

                {metrics.safety && metrics.safety.sensitivity_recall < 0.7 && (
                  <div className="alert alert-danger tiny" style={{ marginTop: 12 }}>
                    This module missed {metrics.safety.missed_diseased_cases} of{' '}
                    {metrics.safety.diseased_samples} diseased cases in evaluation. A negative
                    result here is <strong>not</strong> evidence that disease is absent.
                  </div>
                )}

                {metrics.caveats?.length > 0 && (
                  <details style={{ marginTop: 10 }}>
                    <summary className="tiny muted" style={{ cursor: 'pointer' }}>
                      Evaluation caveats ({metrics.caveats.length})
                    </summary>
                    <ul className="tiny muted" style={{ paddingLeft: 18, marginTop: 8 }}>
                      {metrics.caveats.map((caveat) => (
                        <li key={caveat}>{caveat}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </>
            ) : (
              <p className="small muted" style={{ margin: 0 }}>
                Accuracy has not been measured for this module in this deployment, so no
                performance claim is made.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
