import { useCallback, useEffect, useRef, useState } from 'react';
import { bridgeApi, errorMessage } from '../api/client';
import useResourceStream from '../hooks/useResourceStream';
import ResourceCard from '../components/ResourceCard';
import ResourceMap from '../components/ResourceMap';

const TYPES = [
  { key: '', label: 'All' },
  { key: 'HOSPITAL', label: 'Hospitals' },
  { key: 'EMERGENCY_DEPARTMENT', label: 'Emergency' },
  { key: 'AMBULANCE', label: 'Ambulances' },
  { key: 'BLOOD_BANK', label: 'Blood banks' },
  { key: 'PHARMACY', label: 'Pharmacies' },
  { key: 'SHELTER', label: 'Shelters' },
];

// Chennai city centre: used only when the browser denies geolocation, and the
// UI says so rather than pretending these distances are from the user.
const FALLBACK = { lat: 13.0604, lng: 80.2496, label: 'Chennai city centre' };
const POLL_MS = 8000;

export default function EmergencyNetwork() {
  const [resources, setResources] = useState([]);
  const [type, setType] = useState('');
  const [radiusKm, setRadiusKm] = useState(15);
  const [origin, setOrigin] = useState(null);
  const [locating, setLocating] = useState(true);
  const [usingFallback, setUsingFallback] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState('map');
  const [flash, setFlash] = useState(null);

  const filters = useRef({ type, radiusKm, origin });
  filters.current = { type, radiusKm, origin };

  // --- geolocation --------------------------------------------------------
  useEffect(() => {
    if (!navigator.geolocation) {
      setOrigin(FALLBACK);
      setUsingFallback(true);
      setLocating(false);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin({
          lat: position.coords.latitude,
          lng: position.coords.longitude,
          label: 'Your location',
        });
        setLocating(false);
      },
      () => {
        setOrigin(FALLBACK);
        setUsingFallback(true);
        setLocating(false);
      },
      { timeout: 8000, maximumAge: 60000 },
    );
  }, []);

  // --- fetching -----------------------------------------------------------
  const load = useCallback(async (quiet = false) => {
    const { type: t, radiusKm: r, origin: o } = filters.current;
    if (!o) return;
    if (!quiet) setLoading(true);
    try {
      const data = await bridgeApi.nearby({
        lat: o.lat,
        lng: o.lng,
        radiusKm: r,
        type: t || undefined,
      });
      setResources(data);
      setError('');
    } catch (err) {
      setError(errorMessage(err, 'Could not load emergency resources.'));
    } finally {
      if (!quiet) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (origin) load();
  }, [origin, type, radiusKm, load]);

  // --- live updates -------------------------------------------------------
  const handleUpdate = useCallback((updated) => {
    setResources((current) => {
      const index = current.findIndex((item) => item.id === updated.id);
      if (index === -1) {
        return current;
      }
      const next = [...current];
      // The broadcast carries no distance (the server has no caller location),
      // so keep the distance already computed for this user.
      next[index] = { ...updated, distanceKm: current[index].distanceKm };
      return next;
    });
    setFlash(updated.id);
    setTimeout(() => setFlash((id) => (id === updated.id ? null : id)), 2000);
  }, []);

  const { connected } = useResourceStream(handleUpdate);

  // Polling fallback: only runs while the socket is down.
  useEffect(() => {
    if (connected) return undefined;
    const timer = setInterval(() => load(true), POLL_MS);
    return () => clearInterval(timer);
  }, [connected, load]);

  const counts = resources.reduce((acc, item) => {
    acc[item.type] = (acc[item.type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="container">
      <div className="row spread" style={{ alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ marginBottom: 4 }}>Emergency Resource Network</h1>
          <p className="muted" style={{ marginBottom: 0 }}>
            Live availability of nearby hospitals, ambulances, blood banks, pharmacies and
            shelters.
          </p>
        </div>
        <span
          className={`badge ${connected ? 'badge-ok' : 'badge-warn'}`}
          title={
            connected
              ? 'Live updates over WebSocket'
              : `WebSocket unavailable - refreshing every ${POLL_MS / 1000}s`
          }
        >
          {connected ? '● Live' : `↻ Polling ${POLL_MS / 1000}s`}
        </span>
      </div>

      <div className="alert alert-warn" style={{ marginTop: 16 }}>
        <strong>Demo data.</strong> These records are seeded samples for demonstration, not a
        verified live feed. In a real emergency call your local emergency number
        (<strong>108</strong> or <strong>112</strong> in India) rather than relying on this
        page.
      </div>

      {error && <div className="alert alert-danger">{error}</div>}

      {usingFallback && !locating && (
        <div className="alert alert-info tiny">
          Location unavailable, so results are centred on {FALLBACK.label}. Distances are
          measured from there, not from you.
        </div>
      )}

      {/* filters */}
      <div className="card" style={{ marginTop: 16 }}>
        <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
          {TYPES.map((option) => (
            <button
              key={option.key || 'all'}
              type="button"
              className={type === option.key ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '6px 14px', fontSize: 13 }}
              onClick={() => setType(option.key)}
            >
              {option.label}
              {option.key && counts[option.key] ? ` (${counts[option.key]})` : ''}
            </button>
          ))}
        </div>

        <div className="row spread" style={{ marginTop: 14, flexWrap: 'wrap', gap: 12 }}>
          <div className="row" style={{ gap: 10, flex: 1, minWidth: 240 }}>
            <label htmlFor="radius" style={{ marginBottom: 0, whiteSpace: 'nowrap' }}>
              Radius {radiusKm} km
            </label>
            <input
              id="radius"
              type="range"
              min={1}
              max={50}
              value={radiusKm}
              onChange={(event) => setRadiusKm(Number(event.target.value))}
              style={{ flex: 1 }}
            />
          </div>
          <div className="row" style={{ gap: 8 }}>
            <button
              type="button"
              className={view === 'map' ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '6px 14px', fontSize: 13 }}
              onClick={() => setView('map')}
            >
              Map
            </button>
            <button
              type="button"
              className={view === 'list' ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '6px 14px', fontSize: 13 }}
              onClick={() => setView('list')}
            >
              List
            </button>
            <button
              type="button"
              className="btn-ghost"
              style={{ padding: '6px 14px', fontSize: 13 }}
              onClick={() => load()}
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      {locating || loading ? (
        <p className="muted" style={{ marginTop: 20 }}>
          {locating ? 'Finding your location…' : 'Loading resources…'}
        </p>
      ) : resources.length === 0 ? (
        <div className="card" style={{ marginTop: 16 }}>
          <p className="muted" style={{ margin: 0 }}>
            No resources within {radiusKm} km. Try widening the radius or clearing the filter.
          </p>
        </div>
      ) : (
        <>
          {view === 'map' && (
            <div style={{ marginTop: 16 }}>
              <ResourceMap resources={resources} origin={origin} flashId={flash} />
            </div>
          )}
          <div className="grid grid-3" style={{ marginTop: 16 }}>
            {resources.map((resource) => (
              <ResourceCard
                key={resource.id}
                resource={resource}
                highlight={flash === resource.id}
                onUpdated={handleUpdate}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
