import React from 'react';

export default function StatusBadge({ status }) {
  const s = (status || '').toString().toLowerCase();

  let bg = '#F1F5F9';
  let color = '#475569';
  let dot = '#94A3B8';

  if (s === 'critical' || s === 'breached' || s === 'failed' || s === 'cancelled') {
    bg = '#FDE8E6';
    color = '#EA341F';
    dot = '#EA341F';
  } else if (s === 'high' || s === 'delayed' || s === 'at risk' || s === 'investigating' || s === 'disputed') {
    bg = '#FEF3D6';
    color = '#B45309';
    dot = '#F59E0B';
  } else if (s === 'delivered' || s === 'settled' || s === 'resolved' || s === 'active' || s === 'on time' || s === 'passed') {
    bg = '#EAF7EE';
    color = '#1E8E3E';
    dot = '#10B981';
  } else if (s === 'in transit' || s === 'dispatched' || s === 'in progress' || s === 'approved') {
    bg = '#EBF3FC';
    color = '#1967D2';
    dot = '#2563EB';
  } else if (s === 'medium') {
    bg = '#EDE9FE';
    color = '#6D28D9';
    dot = '#7C3AED';
  }

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 8px',
        borderRadius: 9999,
        background: bg,
        color: color,
        fontSize: '11px',
        fontWeight: 700,
        letterSpacing: '0.01em',
        textTransform: 'capitalize',
        whiteSpace: 'nowrap',
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: dot }} />
      {status}
    </span>
  );
}
