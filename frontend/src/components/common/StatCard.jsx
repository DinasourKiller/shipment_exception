import React from 'react';

export default function StatCard({ title, value, change, isPositive, subtitle, icon: Icon, color = '#18217E' }) {
  return (
    <div className="kpi-card">
      <div className="kpi-header">
        <div className="kpi-title-wrap">
          {Icon && (
            <div
              className="kpi-icon-wrap"
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: `${color}14`,
                color: color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Icon size={17} />
            </div>
          )}
          <span style={{ fontSize: 13, fontWeight: 600, color: '#475569' }}>{title}</span>
        </div>
        {change && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              padding: '2px 7px',
              borderRadius: 6,
              background: isPositive ? '#EAF7EE' : '#FDE8E6',
              color: isPositive ? '#1E8E3E' : '#EA341F',
            }}
          >
            {change}
          </span>
        )}
      </div>
      <div style={{ fontSize: 24, fontWeight: 800, color: 'var(--color-midnight, #070724)', letterSpacing: '-0.02em', marginBottom: 4 }}>
        {value}
      </div>
      {subtitle && (
        <div style={{ fontSize: 11.5, color: '#64748B' }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}
