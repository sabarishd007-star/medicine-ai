import { useState } from 'react';
import { bridgeApi, errorMessage } from '../api/client';
import { useAuth } from '../context/AuthContext';

const STATUS_STYLE = {
  OPEN: 'badge-ok',
  AVAILABLE: 'badge-ok',
  LIMITED: 'badge-warn',
  BUSY: 'badge-warn',
  FULL: 'badge-danger',
  CLOSED: 'badge-danger',
  UNKNOWN: 'badge-muted',
};

const TYPE_LABEL = {
  HOSPITAL: 'Hospital',
  EMERGENCY_DEPARTMENT: 'Emergency dept',
  BLOOD_BANK: 'Blood bank',
  AMBULANCE: 'Ambulance',
  PHARMACY: 'Pharmacy',
  SHELTER: 'Shelter',
};

/** Blood groups below this are shown in red: critically low stock. */
const LOW_STOCK = 5;

export default function ResourceCard({ resource, highlight, onUpdated }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const post = async (payload) => {
    setBusy(true);
    setError('');
    try {
      const updated = await bridgeApi.updateStatus(resource.id, payload);
      onUpdated?.(updated);
    } catch (err) {
      setError(errorMessage(err, 'Update failed.'));
    } finally {
      setBusy(false);
    }
  };

  const isAmbulance = resource.type === 'AMBULANCE';
  const available = resource.ambulance?.available;

  return (
    <div
      className="card"
      style={{
        borderColor: highlight ? 'var(--brand)' : 'var(--border)',
        boxShadow: highlight ? '0 0 0 3px rgba(31,111,235,0.18)' : 'var(--shadow)',
        transition: 'box-shadow 0.3s ease, border-color 0.3s ease',
      }}
    >
      <div className="row spread" style={{ alignItems: 'flex-start' }}>
        <div>
          <span className="tiny muted">{TYPE_LABEL[resource.type] ?? resource.type}</span>
          <h3 style={{ margin: '2px 0 4px', fontSize: 15 }}>{resource.name}</h3>
        </div>
        <span className={`badge ${STATUS_STYLE[resource.status] ?? 'badge-muted'}`}>
          {resource.status}
        </span>
      </div>

      {resource.distanceKm != null && (
        <p className="tiny muted" style={{ margin: '0 0 6px' }}>
          {resource.distanceKm.toFixed(1)} km away
        </p>
      )}

      {/* Capacity */}
      {resource.capacityAvailable != null && resource.capacityTotal != null && (
        <div style={{ marginBottom: 8 }}>
          <div className="tiny muted">
            {resource.capacityAvailable} of {resource.capacityTotal} beds free
          </div>
          <div className="bar" style={{ marginTop: 4 }}>
            <span
              style={{
                width: `${(resource.capacityAvailable / resource.capacityTotal) * 100}%`,
                background:
                  resource.capacityAvailable === 0
                    ? 'var(--danger)'
                    : resource.capacityAvailable / resource.capacityTotal < 0.2
                      ? 'var(--warn)'
                      : 'var(--ok)',
              }}
            />
          </div>
        </div>
      )}

      {/* Ambulance */}
      {isAmbulance && resource.ambulance && (
        <p className="small" style={{ margin: '0 0 8px' }}>
          <strong style={{ color: available ? 'var(--ok)' : 'var(--warn)' }}>
            {available ? 'Available now' : 'On a call'}
          </strong>
          {resource.ambulance.currentLocation && (
            <span className="muted"> · {resource.ambulance.currentLocation}</span>
          )}
        </p>
      )}

      {/* Blood stock */}
      {resource.bloodInventory?.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          <div className="tiny muted" style={{ marginBottom: 4 }}>
            Blood units in stock
          </div>
          <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
            {resource.bloodInventory.map((stock) => (
              <span
                key={stock.bloodGroup}
                className={`badge ${stock.unitsAvailable < LOW_STOCK ? 'badge-danger' : 'badge-ok'}`}
                title={
                  stock.unitsAvailable < LOW_STOCK ? 'Critically low stock' : 'Adequate stock'
                }
              >
                {stock.bloodGroup} {stock.unitsAvailable}
              </span>
            ))}
          </div>
        </div>
      )}

      {resource.notes && (
        <p className="tiny muted" style={{ margin: '0 0 8px' }}>
          {resource.notes}
        </p>
      )}

      <div className="row spread" style={{ marginTop: 10 }}>
        {resource.contactNumber ? (
          <a href={`tel:${resource.contactNumber}`} className="small">
            Call {resource.contactNumber}
          </a>
        ) : (
          <span />
        )}
        {resource.stale && (
          <span className="badge badge-warn" title="No update in the last 30 minutes">
            Stale
          </span>
        )}
      </div>

      {/* Staff controls: only for signed-in users, since a change is broadcast
          to everyone currently viewing the network. */}
      {user && (
        <div style={{ borderTop: '1px solid var(--border)', marginTop: 12, paddingTop: 10 }}>
          <div className="tiny muted" style={{ marginBottom: 6 }}>
            Staff update
          </div>
          {error && <div className="alert alert-danger tiny">{error}</div>}
          <div className="row" style={{ flexWrap: 'wrap', gap: 6 }}>
            {isAmbulance ? (
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                style={{ padding: '4px 10px', fontSize: 12 }}
                onClick={() => post({ ambulanceAvailable: !available })}
              >
                {busy ? '…' : available ? 'Mark on a call' : 'Mark available'}
              </button>
            ) : (
              <>
                {['OPEN', 'LIMITED', 'FULL', 'CLOSED'].map((status) => (
                  <button
                    key={status}
                    type="button"
                    className="btn-ghost"
                    disabled={busy || resource.status === status}
                    style={{ padding: '4px 10px', fontSize: 12 }}
                    onClick={() => post({ status })}
                  >
                    {status}
                  </button>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
