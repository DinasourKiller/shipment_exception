import React, { useState } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import {
  Home,
  Thermometer,
  Truck,
  CheckCircle2,
  Clock,
  ArrowRight,
  ShieldCheck,
  Package,
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

export default function WarehouseView({ onNavigate }) {
  const { showToast } = useToast();
  const [docks, setDocks] = useState([
    { id: 1, type: 'Refrigerated Cold Bay', truck: 'TRK-2843 (Inbound Diverted)', temp: '-20.5°C Verified', status: 'Reserved for Emergency Intercept' },
    { id: 2, type: 'Refrigerated Bay', truck: 'TRK-8812', temp: '-18.0°C', status: 'Loading Pallets' },
    { id: 3, type: 'Standard Dry Bay', truck: 'TRK-1092', temp: 'Ambient', status: 'Staged' },
    { id: 4, type: 'Standard Dry Bay', truck: 'Empty', temp: 'N/A', status: 'Available' },
    { id: 5, type: 'Cross-Dock Express', truck: 'Empty', temp: 'N/A', status: 'Available' },
    { id: 6, type: 'Heavy Cargo Bay', truck: 'TRK-4401', temp: 'Ambient', status: 'Unloading' },
    { id: 7, type: 'Standard Dry Bay', truck: 'Empty', temp: 'N/A', status: 'Available' },
    { id: 8, type: 'Inspection & Quarantine', truck: 'Empty', temp: 'N/A', status: 'Available' },
  ]);

  const handleAllocate = (dockId) => {
    showToast(`Dock #${dockId} allocated to emergency relief unit`, 'success');
  };

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Banner */}
      <div style={{ background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
              Dallas Central Logistics Hub (WH-DAL-01)
            </h2>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
              Real-time dock bay management, cold-chain pre-checks, cross-dock diversion intake, and driver gate passes.
            </p>
          </div>
          <button
            onClick={() => onNavigate('delivery')}
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
            <CheckCircle2 size={15} />
            <span>Driver Gate Handover</span>
          </button>
        </div>
      </div>

      {/* Dock Doors Grid (1-8) */}
      <div>
        <h3 style={{ margin: '0 0 12px 0', fontSize: 14, fontWeight: 700, color: '#0F172A' }}>
          Dock Bay Allocation &amp; Turn-Around Status (Doors 1–8)
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
          {docks.map((d) => {
            const isEmergency = d.id === 1;
            const isOccupied = d.truck !== 'Empty';
            return (
              <div
                key={d.id}
                className="panel"
                style={{
                  borderTop: `4px solid ${isEmergency ? '#EA341F' : isOccupied ? '#18217E' : '#10B981'}`,
                  padding: '14px 16px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 800, color: '#0F172A' }}>Door #{d.id}</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: isOccupied ? '#18217E' : '#166534', background: isOccupied ? '#EEF2FF' : '#EAF7EE', padding: '1px 6px', borderRadius: 4 }}>
                    {isOccupied ? 'Occupied' : 'Ready'}
                  </span>
                </div>

                <div style={{ fontSize: 11, color: '#64748B', marginBottom: 4 }}>{d.type}</div>
                <div style={{ fontSize: 12.5, fontWeight: 700, color: isEmergency ? '#EA341F' : '#0F172A', marginBottom: 8 }}>
                  {d.truck}
                </div>

                <div style={{ fontSize: 11, color: '#475569', display: 'flex', alignItems: 'center', gap: 4, marginBottom: 10 }}>
                  <Thermometer size={12} color="#3B82F6" />
                  <span>{d.temp}</span>
                </div>

                <div style={{ paddingTop: 8, borderTop: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 10.5, color: '#64748B' }}>{d.status}</span>
                  {!isOccupied && (
                    <button
                      onClick={() => handleAllocate(d.id)}
                      style={{ padding: '3px 8px', borderRadius: 4, border: '1px solid #CBD5E1', background: '#FFF', fontSize: 10.5, fontWeight: 600, cursor: 'pointer' }}
                    >
                      Assign
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
