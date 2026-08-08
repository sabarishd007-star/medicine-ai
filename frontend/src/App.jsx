import React, { useState } from 'react';
import axios from 'axios';

function App() {
  const [formData, setFormData] = useState({
    patientName: '',
    patientAge: '',
    disease: 'brain_tumor',
  });
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return alert('Please select an image file');

    const payload = new FormData();
    payload.append('patientName', formData.patientName);
    payload.append('patientAge', formData.patientAge);
    payload.append('disease', formData.disease);
    payload.append('file', file);

    setLoading(true);
    setResult(null);

    try {
      const response = await axios.post('http://localhost:8080/api/scans/analyze', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(response.data);
    } catch (err) {
      alert('Error analyzing scan: ' + (err.response?.data?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '40px auto', fontFamily: 'sans-serif', padding: '20px' }}>
      <h2>MediScan AI - Medical Scan Analysis</h2>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
        <div>
          <label>Patient Name:</label><br />
          <input
            type="text"
            required
            style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            value={formData.patientName}
            onChange={(e) => setFormData({ ...formData, patientName: e.target.value })}
          />
        </div>

        <div>
          <label>Patient Age:</label><br />
          <input
            type="number"
            required
            style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            value={formData.patientAge}
            onChange={(e) => setFormData({ ...formData, patientAge: e.target.value })}
          />
        </div>

        <div>
          <label>Target Condition:</label><br />
          <select
            style={{ width: '100%', padding: '8px', marginTop: '5px' }}
            value={formData.disease}
            onChange={(e) => setFormData({ ...formData, disease: e.target.value })}
          >
            <option value="brain_tumor">Brain Tumor (MRI)</option>
            <option value="pneumonia">Pneumonia (Chest X-Ray)</option>
          </select>
        </div>

        <div>
          <label>Upload Medical Scan (JPG/PNG):</label><br />
          <input
            type="file"
            accept="image/*"
            required
            style={{ marginTop: '5px' }}
            onChange={(e) => setFile(e.target.files[0])}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{ padding: '10px 20px', background: '#0066cc', color: '#fff', border: 'none', cursor: 'pointer' }}
        >
          {loading ? 'Analyzing Scan...' : 'Analyze Scan'}
        </button>
      </form>

      {result && (
        <div style={{ marginTop: '30px', padding: '15px', border: '1px solid #ccc', borderRadius: '5px' }}>
          <h3>Analysis Results</h3>
          <p><strong>Prediction:</strong> {result.prediction}</p>
          <p><strong>Confidence:</strong> {result.confidence}%</p>
          <p><strong>Status:</strong> {result.is_conclusive ? 'Conclusive' : 'Inconclusive'}</p>
          {result.report_pdf_path && (
            <p><strong>Generated Report:</strong> {result.report_pdf_path}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
