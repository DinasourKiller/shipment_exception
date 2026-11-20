import React, { useState } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import {
  Users,
  ShieldCheck,
  Plus,
  Key,
  Lock,
  CheckCircle,
} from 'lucide-react';
import { useToast } from '../context/ToastContext';

export default function UsersView() {
  const { showToast } = useToast();
  const [userList, setUserList] = useState([
    { id: 'USR-101', name: 'Bima Ary', email: 'admin@controltower.corp', role: 'System Administrator', status: 'active', lastLogin: '10m ago' },
    { id: 'USR-102', name: 'Sarah Lin', email: 'analyst@controltower.corp', role: 'Control Tower Analyst', status: 'active', lastLogin: '25m ago' },
    { id: 'USR-104', name: 'Elena Rostova', email: 'dispatcher@controltower.corp', role: 'Dispatcher / Planner', status: 'active', lastLogin: '1h ago' },
    { id: 'USR-103', name: 'Marcus Vance', email: 'carrier@controltower.corp', role: 'Carrier Operations User', status: 'active', lastLogin: '45m ago' },
    { id: 'USR-105', name: 'Carlos Mendoza', email: 'manager@controltower.corp', role: 'Warehouse Supervisor', status: 'active', lastLogin: '2h ago' },
  ]);

  const toggleStatus = (id) => {
    setUserList((prev) =>
      prev.map((u) =>
        u.id === id ? { ...u, status: u.status === 'active' ? 'inactive' : 'active' } : u
      )
    );
    showToast('User status updated in enterprise RBAC directory', 'info');
  };

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
            Enterprise User Directory &amp; RBAC Access Governance
          </h2>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
            Manage role permissions, tenant scopes, active sessions, and multi-factor authentication policies.
          </p>
        </div>
        <button
          onClick={() => showToast('Invite enterprise user modal opened', 'info')}
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
          <span>Invite Enterprise User</span>
        </button>
      </div>

      {/* Users Table */}
      <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0', textAlign: 'left', color: '#64748B', fontSize: 11, textTransform: 'uppercase' }}>
              <th style={{ padding: '12px 16px' }}>User ID</th>
              <th style={{ padding: '12px 16px' }}>Full Name</th>
              <th style={{ padding: '12px 16px' }}>Email Address</th>
              <th style={{ padding: '12px 16px' }}>Assigned RBAC Role</th>
              <th style={{ padding: '12px 16px' }}>Status</th>
              <th style={{ padding: '12px 16px' }}>Last Activity</th>
              <th style={{ padding: '12px 16px', textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {userList.map((u) => (
              <tr key={u.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                <td style={{ padding: '12px 16px', fontWeight: 700, color: '#18217E' }}>{u.id}</td>
                <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0F172A' }}>{u.name}</td>
                <td style={{ padding: '12px 16px', color: '#475569' }}>{u.email}</td>
                <td style={{ padding: '12px 16px' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#18217E', background: '#EEF2FF', padding: '2px 8px', borderRadius: 6 }}>
                    {u.role}
                  </span>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  <StatusBadge status={u.status} />
                </td>
                <td style={{ padding: '12px 16px', color: '#64748B', fontSize: 11 }}>{u.lastLogin}</td>
                <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                  <button
                    onClick={() => toggleStatus(u.id)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 6,
                      border: '1px solid #CBD5E1',
                      background: '#FFF',
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: 'pointer',
                      color: u.status === 'active' ? '#EA341F' : '#166534',
                    }}
                  >
                    {u.status === 'active' ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
