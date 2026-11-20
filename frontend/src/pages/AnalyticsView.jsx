import React from 'react';
import StatCard from '../components/common/StatCard';
import {
  BarChart3,
  TrendingUp,
  Truck,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Download,
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

export default function AnalyticsView() {
  const { showToast } = useToast();

  const carriersScorecard = [
    { name: 'Bridges Global Logistics (CAR-01)', otd: '97.2%', exceptions: 3, disputeRate: '1.2%', rating: 'A+ (Elite Partner)' },
    { name: 'Swift Logistics Corp (CAR-02)', otd: '93.8%', exceptions: 8, disputeRate: '4.5%', rating: 'A (Compliant)' },
    { name: 'Apex Freightways (CAR-03)', otd: '89.4%', exceptions: 14, disputeRate: '8.1%', rating: 'B (Under Review)' },
    { name: 'Continental Express (CAR-04)', otd: '96.1%', exceptions: 4, disputeRate: '1.8%', rating: 'A+ (Elite Partner)' },
  ];

  const rootCauses = [
    { cause: 'Traffic & Corridor Congestion', count: 48, percentage: '38%' },
    { cause: 'Mechanical & Compressor Faults', count: 32, percentage: '25%' },
    { cause: 'Warehouse Dock Dwell Delays', count: 24, percentage: '19%' },
    { cause: 'Weather & Interstate Detours', count: 14, percentage: '11%' },
    { cause: 'Documentation Defect / Customs', count: 9, percentage: '7%' },
  ];

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
            Operational Intelligence &amp; Carrier Analytics
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
            Root cause Pareto distributions, carrier reliability scorecards, and historical deviation trends.
          </p>
        </div>
        <button
          onClick={() => showToast('Analytics executive summary report exported (PDF)', 'success')}
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
          <Download size={14} />
          <span>Export Executive PDF</span>
        </button>
      </div>

      {/* Grid: Scorecards & Pareto Causes */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1.2fr', gap: 20 }}>
        {/* Carrier Scorecards */}
        <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid #E2E8F0' }}>
            <span className="panel-title">Carrier Performance Scorecards</span>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', color: '#64748B', textAlign: 'left', fontSize: 11 }}>
                <th style={{ padding: '10px 14px' }}>Carrier Partner</th>
                <th style={{ padding: '10px 14px' }}>On-Time Rate</th>
                <th style={{ padding: '10px 14px' }}>Exceptions</th>
                <th style={{ padding: '10px 14px' }}>Dispute Rate</th>
                <th style={{ padding: '10px 14px' }}>Rating</th>
              </tr>
            </thead>
            <tbody>
              {carriersScorecard.map((c, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#0F172A' }}>{c.name}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 700, color: '#166534' }}>{c.otd}</td>
                  <td style={{ padding: '10px 14px', color: '#64748B' }}>{c.exceptions}</td>
                  <td style={{ padding: '10px 14px', color: '#B45309' }}>{c.disputeRate}</td>
                  <td style={{ padding: '10px 14px', fontWeight: 600, color: '#18217E' }}>{c.rating}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pareto Root Causes */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Root Cause Pareto Distribution</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {rootCauses.map((rc, idx) => (
              <div key={idx}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                  <span>{rc.cause}</span>
                  <span style={{ fontWeight: 700, color: '#0F172A' }}>{rc.count} incidents ({rc.percentage})</span>
                </div>
                <div style={{ height: 6, background: '#E2E8F0', borderRadius: 3, overflow: 'hidden' }}>
                  <div style={{ width: rc.percentage, height: '100%', background: '#18217E', borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
