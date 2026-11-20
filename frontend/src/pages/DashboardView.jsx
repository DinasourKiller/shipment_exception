import React, { useState, useEffect } from 'react';
import StatCard from '../components/common/StatCard';
import StatusBadge from '../components/common/StatusBadge';
import LiveMap from '../components/common/LiveMap';
import {
  Package,
  Truck,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  ShieldCheck,
  Radio,
  Flame,
} from 'lucide-react';
import api from '../services/api';

export default function DashboardView({ onNavigate }) {
  const [shipments, setShipments] = useState([]);
  const [exceptions, setExceptions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [shipRes, excRes] = await Promise.all([
          api.getShipments({ limit: 6 }),
          api.getExceptions({ limit: 4 }),
        ]);

        if (shipRes.ok && shipRes.data?.data) {
          setShipments(shipRes.data.data.items || shipRes.data.data);
        } else {
          // Fallback realistic seed shipments
          setShipments([
            { id: 'SHP-9821', tracking_number: 'BRG-2843', origin: 'Dallas, TX', destination: 'Denver, CO', carrier: 'Bridges Global', status: 'delayed', priority: 'critical', temperature: '-14.2°C' },
            { id: 'SHP-8812', tracking_number: 'BRG-1092', origin: 'Memphis, TN', destination: 'Chicago, IL', carrier: 'Swift Logistics', status: 'in transit', priority: 'high', temperature: '21.0°C' },
            { id: 'SHP-7741', tracking_number: 'BRG-4401', origin: 'Houston, TX', destination: 'Atlanta, GA', carrier: 'Apex Freight', status: 'in transit', priority: 'medium', temperature: '20.5°C' },
            { id: 'SHP-6629', tracking_number: 'BRG-7719', origin: 'Little Rock, AR', destination: 'New York, NY', carrier: 'Continental Express', status: 'delivered', priority: 'low', temperature: '4.1°C' },
            { id: 'SHP-5510', tracking_number: 'BRG-9023', origin: 'Dallas, TX', destination: 'Los Angeles, CA', carrier: 'Bridges Global', status: 'in transit', priority: 'medium', temperature: '19.8°C' },
          ]);
        }

        if (excRes.ok && excRes.data?.data) {
          setExceptions(excRes.data.data.items || excRes.data.data);
        } else {
          setExceptions([
            { id: 'EXC-101', exception_type: 'Temperature Breach', severity: 'critical', status: 'investigating', shipment_ref: 'BRG-2843', sla_countdown: '18m left' },
            { id: 'EXC-102', exception_type: 'Route Deviation', severity: 'high', status: 'action_required', shipment_ref: 'BRG-1092', sla_countdown: '1h 14m' },
            { id: 'EXC-103', exception_type: 'Excessive Dwell Time', severity: 'medium', status: 'open', shipment_ref: 'BRG-4401', sla_countdown: '3h 20m' },
          ]);
        }
      } catch (e) {
        console.warn('Dashboard load error:', e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Critical Alert Banner if thermal spike exists */}
      <div
        style={{
          background: 'linear-gradient(90deg, #FDE8E6 0%, #FEF2F2 100%)',
          border: '1px solid #FCA5A5',
          borderRadius: 12,
          padding: '12px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: '#EA341F', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFF' }}>
            <Flame size={18} />
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#991B1B' }}>
              Active Incident: Critical Thermal Breach Detected on BRG-2843
            </div>
            <div style={{ fontSize: 12, color: '#7F1D1D' }}>
              BioPharma Cryo Consignment rose to -14.2°C (mandatory SLA limit -20.0°C). Secondary compressor stall detected.
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => onNavigate('investigation')}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: '#EA341F',
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
            Forensic Triage <ArrowRight size={14} />
          </button>
          <button
            onClick={() => onNavigate('war_room')}
            style={{
              padding: '6px 14px',
              borderRadius: 6,
              background: '#FFFFFF',
              color: '#991B1B',
              border: '1px solid #FCA5A5',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Launch War Room
          </button>
        </div>
      </div>

      {/* Top 4 KPI Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <StatCard
          title="Total Freight Shipments"
          value="12,847"
          change="+12.4%"
          isPositive={true}
          subtitle="All active multi-modal corridors"
          icon={Package}
          color="#18217E"
        />
        <StatCard
          title="Active Deliveries"
          value="426"
          change="+4.2%"
          isPositive={true}
          subtitle="Connected GPS/IoT telemetry units"
          icon={Truck}
          color="#2563EB"
        />
        <StatCard
          title="Fleet Utilization Rate"
          value="87.3%"
          change="+2.1%"
          isPositive={true}
          subtitle="Regional capacity load factor"
          icon={TrendingUp}
          color="#10B981"
        />
        <StatCard
          title="On-Time Delivery (OTD)"
          value="94.8%"
          change="+1.8%"
          isPositive={true}
          subtitle="SLA benchmark threshold: 95.0%"
          icon={ShieldCheck}
          color="#8C2527"
        />
      </div>

      {/* Center Section: Real-World Map & Hub Capacities */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
        {/* Real-World Map Panel */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header">
            <div className="panel-title-wrap">
              <span className="panel-title">Real-World Fleet Telemetry (Continental Corridors)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#166534', background: '#EAF7EE', padding: '2px 8px', borderRadius: 9999 }}>
                ● 500 Carriers Active
              </span>
              <button
                onClick={() => onNavigate('tracking')}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#18217E',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                Expand <ExternalLink size={13} />
              </button>
            </div>
          </div>
          <LiveMap height="400px" interactive={true} />
        </div>

        {/* Hub Capacity & Active Blockers */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <div className="panel-header">
              <div className="panel-title-wrap">
                <span className="panel-title">Hub Capacity &amp; Dock Utilization</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                  <span>Dallas Central SuperHub (WH-DAL-01)</span>
                  <span style={{ color: '#18217E', fontWeight: 700 }}>82%</span>
                </div>
                <div style={{ height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: '82%', height: '100%', background: '#18217E', borderRadius: 4 }} />
                </div>
                <div style={{ fontSize: 10.5, color: '#64748B', marginTop: 3 }}>Bays: 7/8 occupied • 2 diverted trucks staged</div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                  <span>Memphis Intermodal Nexus</span>
                  <span style={{ color: '#EA341F', fontWeight: 700 }}>91% High</span>
                </div>
                <div style={{ height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: '91%', height: '100%', background: '#EA341F', borderRadius: 4 }} />
                </div>
                <div style={{ fontSize: 10.5, color: '#64748B', marginTop: 3 }}>Rail transfer delay: 45 min dwell queue</div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                  <span>Chicago Freight Terminal</span>
                  <span style={{ color: '#10B981', fontWeight: 700 }}>74% Optimal</span>
                </div>
                <div style={{ height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: '74%', height: '100%', background: '#10B981', borderRadius: 4 }} />
                </div>
                <div style={{ fontSize: 10.5, color: '#64748B', marginTop: 3 }}>Cross-dock throughput: 140 pallets/hr</div>
              </div>

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                  <span>Little Rock Emergency Cross-Dock</span>
                  <span style={{ color: '#10B981', fontWeight: 700 }}>45% Ready</span>
                </div>
                <div style={{ height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{ width: '45%', height: '100%', background: '#10B981', borderRadius: 4 }} />
                </div>
                <div style={{ fontSize: 10.5, color: '#64748B', marginTop: 3 }}>Available for cold-chain emergency transfer</div>
              </div>
            </div>
          </div>

          <div style={{ marginTop: 20, paddingTop: 14, borderTop: '1px solid #F1F5F9' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>
                Active Dwell Violations
              </span>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#EA341F' }}>
                2 Corridors
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 11, color: '#64748B' }}>
              Dynamic corridor geo-engine detected stationary dwell exceeding 6h SLA limit.
            </p>
          </div>
        </div>
      </div>

      {/* Bottom Section: Active Exceptions & Recent In-Flight Freight */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Open Exception Triage Feed */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title-wrap">
              <span className="panel-title">Active Exception Triage Queue</span>
            </div>
            <button
              onClick={() => onNavigate('exceptions')}
              style={{ background: 'none', border: 'none', color: '#18217E', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
            >
              View All ({exceptions.length})
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {exceptions.map((exc) => (
              <div
                key={exc.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: '1px solid #E2E8F0',
                  background: '#F8FAFC',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <StatusBadge status={exc.severity} />
                    <strong style={{ fontSize: 12.5, color: '#0F172A' }}>{exc.exception_type}</strong>
                  </div>
                  <div style={{ fontSize: 11, color: '#64748B', marginTop: 3 }}>
                    Shipment: <strong style={{ color: '#18217E' }}>{exc.shipment_ref || exc.id}</strong> • SLA breach in: <strong style={{ color: '#EA341F' }}>{exc.sla_countdown || '35m'}</strong>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => onNavigate('investigation')}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      background: '#18217E',
                      color: '#FFF',
                      border: 'none',
                      fontSize: 11,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Triage
                  </button>
                  <button
                    onClick={() => onNavigate('recovery')}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      background: '#FFF',
                      color: '#334155',
                      border: '1px solid #CBD5E1',
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Tender
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Freight Activity */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title-wrap">
              <span className="panel-title">In-Flight Freight Stream</span>
            </div>
            <button
              onClick={() => onNavigate('shipments')}
              style={{ background: 'none', border: 'none', color: '#18217E', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
            >
              All Shipments
            </button>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B', fontSize: 11 }}>
                  <th style={{ padding: '8px 10px' }}>Tracking</th>
                  <th style={{ padding: '8px 10px' }}>Corridor</th>
                  <th style={{ padding: '8px 10px' }}>Carrier</th>
                  <th style={{ padding: '8px 10px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {shipments.map((s) => (
                  <tr key={s.id || s.tracking_number} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '8px 10px', fontWeight: 700, color: '#18217E' }}>
                      {s.tracking_number || s.id}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#334155' }}>
                      {s.origin} → {s.destination}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#64748B' }}>
                      {s.carrier}
                    </td>
                    <td style={{ padding: '8px 10px' }}>
                      <StatusBadge status={s.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
