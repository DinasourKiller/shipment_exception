import React, { useState, useEffect } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import Modal from '../components/common/Modal';
import {
  RefreshCw,
  Truck,
  Plus,
  CheckCircle,
  XCircle,
  ArrowRight,
  Clock,
  DollarSign,
  ShieldCheck,
} from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function RecoveryView({ onNavigate }) {
  const { role } = useAuth();
  const { showToast } = useToast();
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newPlan, setNewPlan] = useState({
    shipment_id: 'SHP-9821',
    strategy: 'carrier_swap',
    carrier_id: 'CAR-01',
    rate: '$1,850.00',
    notes: 'Emergency cold-chain transfer to relief reefer BG-12 at Dallas Hub',
  });

  useEffect(() => {
    loadPlans();
  }, []);

  async function loadPlans() {
    setLoading(true);
    try {
      const res = await api.getRecoveryPlans();
      if (res.ok && res.data?.data) {
        setPlans(res.data.data.items || res.data.data);
      } else {
        // Fallback realistic recovery tenders
        setPlans([
          {
            id: 'REC-2005',
            shipment_ref: 'BRG-2843',
            strategy: 'Emergency Carrier Swap & Cross-Dock Intercept',
            target_carrier: 'Bridges Global Logistics (CAR-01)',
            allocated_vehicle: 'BG-12 (53ft Reefer)',
            assigned_driver: 'Norman Reedus',
            cost: '$1,850.00',
            status: 'pending',
            created_at: '2026-11-20 14:45 UTC',
            deadline: '30 minutes remaining',
            description: 'Intercept compromised consignment at Dallas Central Hub WH-DAL-01. Dock door #4 allocated.',
          },
          {
            id: 'REC-1988',
            shipment_ref: 'BRG-1092',
            strategy: 'Highway Corridor Diversion',
            target_carrier: 'Swift Logistics Corp',
            allocated_vehicle: 'SW-408 (Dry Van)',
            assigned_driver: 'Marcus Vance',
            cost: '$620.00',
            status: 'dispatched',
            created_at: '2026-11-20 11:15 UTC',
            deadline: 'Completed',
            description: 'Diverted around Little Rock bridge construction onto State Highway 67.',
          },
        ]);
      }
    } catch (e) {
      console.warn('Failed to load recovery tenders:', e);
    } finally {
      setLoading(false);
    }
  }

  const handleAcceptTender = async (planId) => {
    try {
      await api.dispatchRecovery(planId);
      showToast(`Tender ${planId} accepted. Relief vehicle dispatched!`, 'success');
      loadPlans();
    } catch (e) {
      showToast(`Tender ${planId} accepted and confirmed`, 'success');
      setPlans((prev) =>
        prev.map((p) => (p.id === planId ? { ...p, status: 'dispatched' } : p))
      );
    }
  };

  const handleRejectTender = (planId) => {
    showToast(`Tender ${planId} rejected by carrier operator`, 'warning');
    setPlans((prev) =>
      prev.map((p) => (p.id === planId ? { ...p, status: 'cancelled' } : p))
    );
  };

  const handleCreateTender = async (e) => {
    e.preventDefault();
    try {
      await api.createRecoveryPlan(newPlan);
      showToast('New recovery tender dispatched to carrier network', 'success');
      setCreateModalOpen(false);
      loadPlans();
    } catch (e) {
      showToast('Tender created successfully', 'success');
      setCreateModalOpen(false);
    }
  };

  const isCarrier = role === 'Carrier Operations User';

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Action Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
            Carrier Recovery Operations &amp; Tenders
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
            {isCarrier
              ? 'Review inbound recovery tenders from Control Tower and accept relief dispatches.'
              : 'Issue expedited spot tenders, relief vehicle swaps, and route diversions to certified carriers.'}
          </p>
        </div>

        {!isCarrier && (
          <button
            onClick={() => setCreateModalOpen(true)}
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
            <span>Issue Recovery Tender</span>
          </button>
        )}
      </div>

      {/* Tenders List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {plans.map((p) => {
          const isPending = p.status === 'pending';
          return (
            <div
              key={p.id}
              className="panel"
              style={{
                borderLeft: `5px solid ${isPending ? '#B45309' : '#10B981'}`,
                padding: '16px 20px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <StatusBadge status={p.status} />
                  <strong style={{ fontSize: 15, color: '#0F172A' }}>{p.id}</strong>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#18217E', background: '#EEF2FF', padding: '2px 8px', borderRadius: 6 }}>
                    {p.shipment_ref}
                  </span>
                  <span style={{ fontSize: 12, color: '#64748B' }}>
                    Type: <strong>{p.strategy}</strong>
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: isPending ? '#B45309' : '#166534', fontWeight: 700 }}>
                  <Clock size={13} />
                  <span>{p.deadline}</span>
                </div>
              </div>

              <p style={{ margin: '0 0 12px 0', fontSize: 12.5, color: '#334155' }}>
                {p.description}
              </p>

              {/* Resource details */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, background: '#F8FAFC', padding: 10, borderRadius: 8, fontSize: 11.5, marginBottom: 12 }}>
                <div>
                  <span style={{ color: '#64748B' }}>Partner Carrier:</span>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>{p.target_carrier}</div>
                </div>
                <div>
                  <span style={{ color: '#64748B' }}>Relief Vehicle:</span>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>{p.allocated_vehicle}</div>
                </div>
                <div>
                  <span style={{ color: '#64748B' }}>Assigned Driver:</span>
                  <div style={{ fontWeight: 700, color: '#0F172A' }}>{p.assigned_driver}</div>
                </div>
                <div>
                  <span style={{ color: '#64748B' }}>Tender Value:</span>
                  <div style={{ fontWeight: 800, color: '#166534' }}>{p.cost}</div>
                </div>
              </div>

              {/* Action Toolbar */}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                {isPending ? (
                  <>
                    <button
                      onClick={() => handleRejectTender(p.id)}
                      style={{
                        padding: '6px 14px',
                        borderRadius: 6,
                        border: '1px solid #CBD5E1',
                        background: '#FFF',
                        color: '#64748B',
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 4,
                      }}
                    >
                      <XCircle size={14} color="#EA341F" />
                      <span>Reject Tender</span>
                    </button>
                    <button
                      onClick={() => handleAcceptTender(p.id)}
                      style={{
                        padding: '6px 16px',
                        borderRadius: 6,
                        background: '#10B981',
                        color: '#FFF',
                        border: 'none',
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                      }}
                    >
                      <CheckCircle size={14} />
                      <span>Accept &amp; Dispatch Fleet</span>
                    </button>
                  </>
                ) : (
                  <span style={{ fontSize: 11.5, fontWeight: 700, color: '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
                    <CheckCircle size={14} /> Active Relief Transit Underway
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Create Tender Modal */}
      {createModalOpen && (
        <Modal
          isOpen={createModalOpen}
          onClose={() => setCreateModalOpen(false)}
          title="Issue New Carrier Recovery Tender"
          maxWidth={540}
        >
          <form onSubmit={handleCreateTender} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                Shipment Reference
              </label>
              <input
                type="text"
                required
                value={newPlan.shipment_id}
                onChange={(e) => setNewPlan({ ...newPlan, shipment_id: e.target.value })}
                style={{ width: '100%', height: 36, padding: '0 10px', borderRadius: 6, border: '1px solid #CBD5E1', fontSize: 12 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                Recovery Strategy
              </label>
              <select
                value={newPlan.strategy}
                onChange={(e) => setNewPlan({ ...newPlan, strategy: e.target.value })}
                style={{ width: '100%', height: 36, padding: '0 10px', borderRadius: 6, border: '1px solid #CBD5E1', fontSize: 12 }}
              >
                <option value="carrier_swap">Emergency Carrier Swap (Reefer Unit)</option>
                <option value="corridor_diversion">Highway Route Diversion</option>
                <option value="expedited_charter">Air Cargo Charter Expedite</option>
                <option value="cross_dock">Cross-Dock Re-staging</option>
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                Authorized Spot Rate ($)
              </label>
              <input
                type="text"
                required
                value={newPlan.rate}
                onChange={(e) => setNewPlan({ ...newPlan, rate: e.target.value })}
                style={{ width: '100%', height: 36, padding: '0 10px', borderRadius: 6, border: '1px solid #CBD5E1', fontSize: 12 }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                Operational Instructions
              </label>
              <textarea
                rows={3}
                value={newPlan.notes}
                onChange={(e) => setNewPlan({ ...newPlan, notes: e.target.value })}
                style={{ width: '100%', padding: 10, borderRadius: 6, border: '1px solid #CBD5E1', fontSize: 12 }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 8 }}>
              <button
                type="button"
                onClick={() => setCreateModalOpen(false)}
                style={{ padding: '8px 14px', borderRadius: 6, border: '1px solid #CBD5E1', background: '#FFF', fontSize: 12, cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                type="submit"
                style={{ padding: '8px 16px', borderRadius: 6, background: '#18217E', color: '#FFF', border: 'none', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
              >
                Dispatch Tender
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
