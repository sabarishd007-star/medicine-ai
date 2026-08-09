import { Link } from 'react-router-dom';
import { Disclaimer } from '../components/Layout';

const STEPS = [
  ['1. Upload', 'Submit an MRI, X-ray or dermoscopy image with basic patient details.'],
  ['2. Analyse', 'A disease-specific CNN runs inference and produces a confidence score.'],
  ['3. Explain', 'Grad-CAM highlights the regions that drove the prediction.'],
  ['4. Report', 'Download a PDF with the finding, confidence, heatmap and guidance.'],
];

export default function Landing() {
  return (
    <div className="container">
      <section style={{ padding: '48px 0 32px', maxWidth: 720 }}>
        <span className="badge badge-muted">Clinical Decision Support</span>
        <h1 style={{ marginTop: 14 }}>
          A fast first read on a medical scan &mdash; with the uncertainty shown, not hidden.
        </h1>
        <p className="muted" style={{ fontSize: 17 }}>
          MediScan AI runs disease-specific CNNs over an uploaded scan and returns a screening
          estimate with a measured confidence score, a Grad-CAM explanation, and a downloadable
          report. Low-confidence results are marked inconclusive rather than forced into an
          answer.
        </p>
        <div className="row" style={{ marginTop: 24 }}>
          <Link to="/register">
            <button type="button" className="btn-primary">
              Create an account
            </button>
          </Link>
          <Link to="/login">
            <button type="button" className="btn-ghost">
              Log in
            </button>
          </Link>
        </div>
      </section>

      <section>
        <h2>How it works</h2>
        <div className="grid grid-2" style={{ marginTop: 16 }}>
          {STEPS.map(([title, body]) => (
            <div className="card" key={title}>
              <h3>{title}</h3>
              <p className="muted small" style={{ margin: 0 }}>
                {body}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section style={{ marginTop: 40 }}>
        <h2>What we do not claim</h2>
        <div className="card">
          <ul className="muted small" style={{ margin: 0, paddingLeft: 20 }}>
            <li>
              We do not stage or diagnose disease. Severity is only shown where the underlying
              dataset carries those labels.
            </li>
            <li>
              Accuracy is reported per module from a labelled test set. A module with no
              evaluation reports no number at all.
            </li>
            <li>
              Modules without trained weights are flagged and refuse to return a clinical
              finding.
            </li>
            <li>
              Heart attack detection is out of scope for image screening &mdash; it needs ECG
              data, not a static image.
            </li>
          </ul>
        </div>
        <Disclaimer />
      </section>
    </div>
  );
}
