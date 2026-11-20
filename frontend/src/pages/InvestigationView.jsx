import React, { useState } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import {
  Flame,
  Thermometer,
  Navigation,
  Phone,
  ShieldAlert,
  ArrowRight,
  Clock,
  Radio,
  FileCheck,
  CheckCircle2,
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

export default function InvestigationView({ onNavigate }) {
  const { showToast } = useToast();
  const [carrierCallOpen, setCarrierCallOpen] = useState(false);
  const [escalated, setEscalated] = useState(false);

  const telemetryTimeline = [
    { time: '13:30 UTC', temp: '-21.4°C', speed: '62 mph', status: 'Optimal', location: 'Interstate 30 W, MP 84' },
    { time: '13:50 UTC', temp: '-20.8°C', speed: '60 mph', status: 'Normal', location: 'Interstate 30 W, MP 102' },
    { time: '14:10 UTC', temp: '-19.1°C', speed: '59 mph', status: 'Warning (Threshold -20.0°C)', location: 'Interstate 30 W, MP 120' },
    { time: '14:30 UTC', temp: '-16.5°C', speed: '58 mph', status: 'Critical Breach', location: 'Arkadelphia Exits, MP 138' },
    { time: '14:50 UTC', temp: '-14.2°C', speed: '58 mph', status: 'Critical Breach', location: 'Prescott Highway, MP 156' },
  ];

  const handleEscalate = () => {
    setEscalated(true);
    showToast('Incident escalated to Executive Operations & Legal SLA team', 'warning');
  };

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
              Forensic Investigation: BRG-2843
            </span>
            <StatusBadge status="critical" />
            <span style={{ fontSize: 12, color: '#64748B' }}>Consignment: BioPharma Cryo-Vaccine</span>
          </div>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
            Sensor channel A reported rapid thermal degradation in transit across Arkansas corridor.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => setCarrierCallOpen(true)}
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: '1px solid #CBD5E1',
              background: '#FFFFFF',
              color: '#334155',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Phone size={14} color="#18217E" />
            <span>Call Carrier Dispatch</span>
          </button>
          <button
            onClick={handleEscalate}
            disabled={escalated}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              background: escalated ? '#94A3B8' : '#EA341F',
              color: '#FFFFFF',
              border: 'none',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <ShieldAlert size={14} />
            <span>{escalated ? 'Escalated' : 'Executive Escalation'}</span>
          </button>
          <button
            onClick={() => onNavigate('war_room')}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              background: '#18217E',
              color: '#FFFFFF',
              border: 'none',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Flame size={14} />
            <span>Open War Room</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Telemetry Curve & Sensor Diagnostics */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.8fr 1.2fr', gap: 20 }}>
        {/* Telemetry Sensor Curve Simulation */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title-wrap">
              <span className="panel-title">IoT Telemetry Curve: Core Cargo Temperature (°C)</span>
            </div>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#EA341F', background: '#FDE8E6', padding: '2px 8px', borderRadius: 9999 }}>
              Threshold Ceiling: -20.0°C
            </span>
          </div>

          {/* Graphical visualization representation */}
          <div style={{ background: '#0F172A', borderRadius: 10, padding: '20px', color: '#FFF', position: 'relative', overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#94A3B8', marginBottom: 12 }}>
              <span>13:00 UTC</span>
              <span>13:30 UTC</span>
              <span>14:00 UTC</span>
              <span>14:30 UTC</span>
              <span>15:00 UTC (Current)</span>
            </div>

            {/* Threshold dashed line */}
            <div style={{ position: 'relative', height: 160, display: 'flex', alignItems: 'flex-end', gap: 18, borderBottom: '1px solid #334155' }}>
              <div style={{ position: 'absolute', top: 50, left: 0, right: 0, borderTop: '2px dashed #EF4444', display: 'flex', justifyContent: 'flex-end' }}>
                <span style={{ background: '#EF4444', color: '#FFF', fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 4, transform: 'translateY(-50%)' }}>
                  BREACH LIMIT: -20.0°C
                </span>
              </div>

              {/* Data points visual bars */}
              {[
                { time: '13:00', val: '-22.1°C', h: '35%', color: '#10B981' },
                { time: '13:30', val: '-21.4°C', h: '42%', color: '#10B981' },
                { time: '14:00', val: '-19.1°C', h: '62%', color: '#F59E0B' },
                { time: '14:30', val: '-16.5°C', h: '80%', color: '#EF4444' },
                { time: '15:00', val: '-14.2°C', h: '95%', color: '#DC2626' },
              ].map((bar, idx) => (
                <div key={idx} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', height: '100%', justifyContent: 'flex-end' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, color: bar.color, marginBottom: 4 }}>{bar.val}</span>
                  <div style={{ width: '100%', height: bar.h, background: `linear-gradient(to top, ${bar.color}40, ${bar.color})`, borderRadius: '4px 4px 0 0' }} />
                  <span style={{ fontSize: 9, color: '#64748B', marginTop: 4 }}>{bar.time}</span>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 16, fontSize: 11 }}>
              <div style={{ display: 'flex', gap: 16 }}>
                <span style={{ color: '#10B981' }}>● Compressor Channel 1: Offline (Stall)</span>
                <span style={{ color: '#60A5FA' }}>● Ambient Temp: 28.5°C</span>
              </div>
              <span style={{ color: '#F87171', fontWeight: 700 }}>Telemetry Stream: 1 ping/15s</span>
            </div>
          </div>

          {/* Breadcrumbs Table */}
          <div style={{ marginTop: 20 }}>
            <h4 style={{ margin: '0 0 10px 0', fontSize: 12.5, fontWeight: 700, color: '#0F172A' }}>
              Forensic Telemetry Chronology
            </h4>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11.5 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #E2E8F0', color: '#64748B', textAlign: 'left' }}>
                    <th style={{ padding: '6px 8px' }}>Timestamp</th>
                    <th style={{ padding: '6px 8px' }}>GPS Location</th>
                    <th style={{ padding: '6px 8px' }}>Core Temp</th>
                    <th style={{ padding: '6px 8px' }}>Speed</th>
                    <th style={{ padding: '6px 8px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {telemetryTimeline.map((row, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: '6px 8px', fontWeight: 600 }}>{row.time}</td>
                      <td style={{ padding: '6px 8px', color: '#475569' }}>{row.location}</td>
                      <td style={{ padding: '6px 8px', fontWeight: 700, color: row.temp.startsWith('-1') ? '#EA341F' : '#10B981' }}>
                        {row.temp}
                      </td>
                      <td style={{ padding: '6px 8px' }}>{row.speed}</td>
                      <td style={{ padding: '6px 8px' }}>
                        <span style={{ fontSize: 10.5, fontWeight: 700, color: row.status.includes('Breach') ? '#EA341F' : '#10B981' }}>
                          {row.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Carrier Details & Recommended Plan */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Assigned Carrier &amp; Driver</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: '#64748B' }}>Carrier Organization</span>
                <strong style={{ color: '#0F172A' }}>Bridges Global Logistics (CAR-01)</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: '#64748B' }}>Primary Driver</span>
                <strong style={{ color: '#0F172A' }}>Norman Reedus</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: '#64748B' }}>Equipment</span>
                <strong style={{ color: '#0F172A' }}>Tractor BG-12 / Reefer RF-04</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                <span style={{ color: '#64748B' }}>Driver Contact</span>
                <strong style={{ color: '#18217E' }}>+1 (555) 019-5519</strong>
              </div>
            </div>
          </div>

          <div className="panel" style={{ background: '#EEF2FF', border: '1px solid #C7D2FE' }}>
            <div className="panel-header">
              <span className="panel-title" style={{ color: '#1E1B4B' }}>Mitigation Playbook PB-COLD-04</span>
            </div>
            <p style={{ margin: '0 0 12px 0', fontSize: 12, color: '#3730A3', lineHeight: 1.45 }}>
              Cargo requires immediate cross-dock transfer within 45 minutes to prevent irreversible biological thawing.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 11.5 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#1E1B4B' }}>
                <CheckCircle2 size={13} color="#10B981" /> Emergency Rendezvous: Dallas Central Hub (WH-DAL-01)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#1E1B4B' }}>
                <CheckCircle2 size={13} color="#10B981" /> Relief Reefer Unit: Pre-cooling to -25.0°C
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#1E1B4B' }}>
                <CheckCircle2 size={13} color="#10B981" /> Tender REC-2005 ready for Carrier Dispatch
              </div>
            </div>
            <button
              onClick={() => onNavigate('recovery')}
              style={{
                marginTop: 14,
                width: '100%',
                padding: '8px',
                borderRadius: 6,
                background: '#18217E',
                color: '#FFF',
                border: 'none',
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Issue Emergency Recovery Tender →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
