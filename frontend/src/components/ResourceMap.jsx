/**
 * Lightweight scatter map of nearby resources.
 *
 * Deliberately not a tile map: adding Leaflet/Google Maps would pull in a new
 * dependency and an API key for what the demo needs, which is a spatial sense
 * of what is close. Positions are projected relative to the caller's location
 * with a cos(lat) correction so east-west distances are not exaggerated.
 */

const TYPE_COLOR = {
  HOSPITAL: '#1f6feb',
  EMERGENCY_DEPARTMENT: '#b91c1c',
  BLOOD_BANK: '#be123c',
  AMBULANCE: '#0f766e',
  PHARMACY: '#7c3aed',
  SHELTER: '#b45309',
};

const TYPE_LABEL = {
  HOSPITAL: 'Hospital',
  EMERGENCY_DEPARTMENT: 'Emergency',
  BLOOD_BANK: 'Blood bank',
  AMBULANCE: 'Ambulance',
  PHARMACY: 'Pharmacy',
  SHELTER: 'Shelter',
};

const SIZE = 320;

export default function ResourceMap({ resources, origin, flashId }) {
  if (!origin || resources.length === 0) {
    return null;
  }

  const cosLat = Math.cos((origin.lat * Math.PI) / 180) || 1;
  const points = resources.map((resource) => ({
    resource,
    dx: (resource.longitude - origin.lng) * cosLat,
    dy: resource.latitude - origin.lat,
  }));

  // Scale so the furthest resource sits just inside the edge.
  const extent =
    Math.max(...points.map((p) => Math.max(Math.abs(p.dx), Math.abs(p.dy))), 1e-4) * 1.15;
  const project = (value) => (value / extent) * (SIZE / 2 - 18) + SIZE / 2;

  const rings = [0.33, 0.66, 1];
  const maxKm = Math.max(...resources.map((r) => r.distanceKm ?? 0));

  return (
    <div className="card">
      <div className="row spread" style={{ marginBottom: 10 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>Proximity view</h3>
        <span className="tiny muted">Centred on {origin.label ?? 'your location'}</span>
      </div>

      <div className="row" style={{ gap: 20, alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <svg
          width={SIZE}
          height={SIZE}
          role="img"
          aria-label="Map of nearby emergency resources"
          style={{ background: '#f8fafc', borderRadius: 10, border: '1px solid var(--border)' }}
        >
          {rings.map((ring) => (
            <circle
              key={ring}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={(SIZE / 2 - 18) * ring}
              fill="none"
              stroke="#dbe2ec"
              strokeDasharray="4 4"
            />
          ))}
          {rings.map((ring) => (
            <text
              key={`label-${ring}`}
              x={SIZE / 2 + 4}
              y={SIZE / 2 - (SIZE / 2 - 18) * ring + 12}
              fontSize="9"
              fill="#94a3b8"
            >
              {(maxKm * ring).toFixed(1)} km
            </text>
          ))}

          {/* origin */}
          <circle cx={SIZE / 2} cy={SIZE / 2} r={6} fill="#0f172a" />
          <circle cx={SIZE / 2} cy={SIZE / 2} r={12} fill="none" stroke="#0f172a" opacity="0.3" />

          {points.map(({ resource, dx, dy }) => {
            const cx = project(dx);
            // SVG y grows downward, so north must be negated.
            const cy = SIZE - project(dy);
            const flashing = flashId === resource.id;
            return (
              <g key={resource.id}>
                {flashing && (
                  <circle cx={cx} cy={cy} r={13} fill={TYPE_COLOR[resource.type]} opacity="0.25" />
                )}
                <circle
                  cx={cx}
                  cy={cy}
                  r={flashing ? 8 : 6}
                  fill={TYPE_COLOR[resource.type] ?? '#64748b'}
                  stroke="#fff"
                  strokeWidth="1.5"
                >
                  <title>
                    {resource.name} — {resource.status}
                    {resource.distanceKm != null
                      ? ` (${resource.distanceKm.toFixed(1)} km)`
                      : ''}
                  </title>
                </circle>
              </g>
            );
          })}
        </svg>

        <div>
          <div className="tiny muted" style={{ marginBottom: 8 }}>
            Legend
          </div>
          {Object.entries(TYPE_LABEL).map(([key, label]) => (
            <div key={key} className="row" style={{ gap: 8, marginBottom: 6 }}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: '50%',
                  background: TYPE_COLOR[key],
                  display: 'inline-block',
                }}
              />
              <span className="tiny">{label}</span>
            </div>
          ))}
          <div className="row" style={{ gap: 8, marginTop: 10 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: '#0f172a',
                display: 'inline-block',
              }}
            />
            <span className="tiny">You</span>
          </div>
        </div>
      </div>
    </div>
  );
}
