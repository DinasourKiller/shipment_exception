import React, { useState } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import {
  Truck,
  ShieldCheck,
  Phone,
  Mail,
  Plus,
  CheckCircle2,
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

export default function CarriersView() {
  const { showToast } = useToast();
  const [carriers] = useState([
    {
      id: 'CAR-01',
      name: 'Bridges Global Logistics',
      fleet_size: '142 Vehicles',
      rating: '4.9 / 5.0',
      active_shipments: 48,
      status: 'active',
      contact: 'Marcus Vance',
      phone: '+1 (555) 019-5519',
      insurance: 'Verified ($2M Comprehensive Reefer)',
    },
    {
      id: 'CAR-02',
      name: 'Swift Logistics Corp',
      fleet_size: '320 Vehicles',
      rating: '4.7 / 5.0',
      active_shipments: 92,
      status: 'active',
      contact: 'Norman Reedus',
      phone: '+1 (555) 019-3829',
      insurance: 'Verified ($5M Cargo)',
    },
    {
      id: 'CAR-03',
      name: 'Apex Freightways',
      fleet_size: '88 Vehicles',
      rating: '4.2 / 5.0',
      active_shipments: 22,
      status: 'active',
      contact: 'Dave Miller',
      phone: '+1 (555) 019-1122',
      insurance: 'Verified ($1M Standard)',
    },
    {
      id: 'CAR-04',
      name: 'Continental Express',
      fleet_size: '215 Vehicles',
      rating: '4.8 / 5.0',
      active_shipments: 64,
      status: 'active',
      contact: 'Elena Hayes',
      phone: '+1 (555) 019-4401',
      insurance: 'Verified ($3M Hazmat/Pharma)',
    },
  ]);

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
            Carrier Network &amp; Fleet Capacity Directory
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
            Certified freight partners, active tractors/reefers, safety scorecards, and insurance coverage.
          </p>
        </div>
        <button
          onClick={() => showToast('Onboard partner modal triggered', 'info')}
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
          <Plus size={15} />
          <span>Onboard Carrier Partner</span>
        </button>
      </div>

      {/* Carrier Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
        {carriers.map((c) => (
          <div key={c.id} className="panel" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 32, height: 32, borderRadius: 8, background: '#EEF2FF', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#18217E' }}>
                    <Truck size={17} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: '#0F172A' }}>{c.name}</h3>
                    <div style={{ fontSize: 11, color: '#64748B' }}>Tenant ID: {c.id}</div>
                  </div>
                </div>
              </div>
              <StatusBadge status={c.status} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, background: '#F8FAFC', padding: 10, borderRadius: 8, fontSize: 11.5, marginBottom: 12 }}>
              <div>
                <span style={{ color: '#64748B' }}>Fleet Size</span>
                <div style={{ fontWeight: 700, color: '#0F172A' }}>{c.fleet_size}</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Active In-Flight</span>
                <div style={{ fontWeight: 700, color: '#18217E' }}>{c.active_shipments} loads</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Safety Score</span>
                <div style={{ fontWeight: 700, color: '#166534' }}>{c.rating}</div>
              </div>
            </div>

            <div style={{ fontSize: 11.5, color: '#475569', display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div>Primary Dispatcher: <strong>{c.contact}</strong> ({c.phone})</div>
              <div>Insurance: <span style={{ color: '#166534', fontWeight: 600 }}>{c.insurance}</span></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
