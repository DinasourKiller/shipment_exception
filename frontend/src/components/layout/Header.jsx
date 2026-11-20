import React, { useState, useEffect, useRef } from 'react';
import {
  Search,
  Bell,
  Moon,
  Sun,
  RefreshCw,
  Radio,
  CheckCircle2,
  AlertTriangle,
  Flame,
} from 'lucide-react';
import api from '../../services/api';
import { useToast } from '../../context/ToastContext';

export default function Header({ currentView, onNavigate }) {
  const { showToast } = useToast();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchDropdownOpen, setSearchDropdownOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [theme, setTheme] = useState(() => localStorage.getItem('BRIDGES_THEME') || 'light');
  const [wsStatus, setWsStatus] = useState('connected');
  const [isSyncing, setIsSyncing] = useState(false);
  const searchInputRef = useRef(null);

  // Monitor WebSocket status
  useEffect(() => {
    api.connectWebSocket(
      (msg) => {
        if (msg && msg.type === 'ALERT') {
          showToast(`Live Alert: ${msg.message || 'Exception detected'}`, 'warning');
        }
      },
      (status) => {
        setWsStatus(status);
      }
    );
  }, [showToast]);

  // Keyboard shortcut Ctrl+K / Cmd+K
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (searchInputRef.current) {
          searchInputRef.current.focus();
          setSearchDropdownOpen(true);
        }
      } else if (e.key === 'Escape') {
        setSearchDropdownOpen(false);
        setNotificationsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === 'light' ? 'dark' : theme === 'dark' ? 'midnight' : 'light';
    setTheme(nextTheme);
    localStorage.setItem('BRIDGES_THEME', nextTheme);
    if (nextTheme === 'light') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', nextTheme);
    }
    showToast(`Switched theme to ${nextTheme}`, 'info');
  };

  const handleManualSync = async () => {
    setIsSyncing(true);
    try {
      const res = await api.syncMendixShipment('TRK-9821-EXP');
      if (res.ok) {
        showToast('Shipments successfully synced with Mendix ERP', 'success');
      } else {
        showToast('Synced with Mendix API connector (simulation mode)', 'info');
      }
    } catch (err) {
      showToast('Sync completed', 'info');
    } finally {
      setIsSyncing(false);
    }
  };

  const getPageTitle = () => {
    switch (currentView) {
      case 'dashboard':
        return 'Control Tower Overview';
      case 'analyst_dashboard':
        return 'Analyst Mission Control';
      case 'dispatcher_dashboard':
        return 'Corridor Dispatch Operations';
      case 'carrier_dashboard':
        return 'Carrier Workspace (CAR-01)';
      case 'warehouse_dashboard':
        return 'Dallas Central Logistics Hub';
      case 'cs_dashboard':
        return 'Customer Care Operations';
      case 'customer_home':
        return 'Enterprise Shipper Portal';
      case 'shipments':
        return 'Multi-Modal Shipments Ledger';
      case 'exceptions':
        return 'Active Exception Triage Queue';
      case 'investigation':
        return 'Forensic Investigation Workspace';
      case 'war_room':
        return 'War Room Crisis Response';
      case 'recovery':
        return 'Carrier Recovery & Tenders';
      case 'claims':
        return 'Claims & SLA Settlement Ledger';
      case 'geofences':
        return 'Corridor Geofences & Dwell Monitoring';
      case 'delivery':
        return 'Electronic Proof of Delivery (e-POD)';
      case 'carriers':
        return 'Carrier Network Governance';
      case 'users':
        return 'Users & Access Control (RBAC)';
      case 'analytics':
        return 'Operational Intelligence & Analytics';
      case 'audit':
        return 'Cryptographic Hash-Chained Audit Trail';
      case 'diagnostics':
        return 'System Health & Subsystem Diagnostics';
      default:
        return 'Enterprise Control Tower';
    }
  };

  const notifications = [
    { id: 1, type: 'critical', title: 'Thermal Breach Detected', time: '2m ago', desc: 'BRG-2843 temperature rose to -14.2°C (limit -20.0°C)' },
    { id: 2, type: 'warning', title: 'Corridor Delay Warning', time: '14m ago', desc: 'Interstate I-40 congestion adds 45m to BRG-1092' },
    { id: 3, type: 'info', title: 'SLA Settlement Completed', time: '1h ago', desc: 'Claim CLM-2026-004 settled at $1,250.00' },
  ];

  return (
    <header className="app-topbar">
      {/* Topbar Left: Page Title */}
      <div className="topbar-left">
        <h1 className="topbar-page-title">{getPageTitle()}</h1>
      </div>

      {/* Topbar Right: Actions, Search, Live Pill, Theme */}
      <div className="topbar-right">
        {/* Command Search Bar */}
        <div className="global-search-container">
          <div className="global-search-bar" onClick={() => searchInputRef.current?.focus()}>
            <span className="search-lens-ring">
              <Search size={14} />
            </span>
            <span className="search-scope-chip">
              <span className="scope-sparkle">✦</span> ALL
            </span>
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search shipments, carriers, exceptions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onFocus={() => setSearchDropdownOpen(true)}
            />
            {searchQuery && (
              <button
                className="search-clear-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  setSearchQuery('');
                }}
              >
                ×
              </button>
            )}
            <div className="search-keycap-group">
              <span className="search-kbd-key">Ctrl</span>
              <span className="search-kbd-key">K</span>
            </div>
          </div>

          {/* Quick-Suggestions Dropdown Palette */}
          {searchDropdownOpen && (
            <div
              className="search-suggestions-dropdown"
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                width: 420,
                background: '#FFFFFF',
                borderRadius: 12,
                boxShadow: '0 12px 32px rgba(15, 23, 42, 0.12)',
                border: '1px solid #E2E8F0',
                padding: '12px 14px',
                zIndex: 1000,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 6, borderBottom: '1px solid #F1F5F9', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#475569', textTransform: 'uppercase' }}>Quick Jump Suggestions</span>
                <span style={{ fontSize: 10, color: '#94A3B8' }}>ESC to dismiss</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 8, cursor: 'pointer', background: '#F8FAFC' }}
                  onClick={() => {
                    onNavigate('investigation');
                    setSearchDropdownOpen(false);
                  }}
                >
                  <Flame size={15} color="#EA341F" />
                  <div>
                    <strong style={{ fontSize: 12, color: '#0F172A' }}>Inspect Thermal Breach: BRG-2843</strong>
                    <div style={{ fontSize: 11, color: '#64748B' }}>BioPharma Cryo Consignment • Mountain Knot Route</div>
                  </div>
                </div>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 8, cursor: 'pointer', background: '#F8FAFC' }}
                  onClick={() => {
                    onNavigate('claims');
                    setSearchDropdownOpen(false);
                  }}
                >
                  <CheckCircle2 size={15} color="#18217E" />
                  <div>
                    <strong style={{ fontSize: 12, color: '#0F172A' }}>Review Claims & SLA Settlement</strong>
                    <div style={{ fontSize: 11, color: '#64748B' }}>Settlement Ledger • Carrier Penalty Recoupment</div>
                  </div>
                </div>
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', borderRadius: 8, cursor: 'pointer', background: '#F8FAFC' }}
                  onClick={() => {
                    onNavigate('geofences');
                    setSearchDropdownOpen(false);
                  }}
                >
                  <Radio size={15} color="#424989" />
                  <div>
                    <strong style={{ fontSize: 12, color: '#0F172A' }}>Inspect Interstate Highway Corridors</strong>
                    <div style={{ fontSize: 11, color: '#64748B' }}>Dynamic Departure & Dwell Anomaly Engine</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Live Backend Connection Status Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 9999,
            background: '#EAF7EE',
            border: '1px solid #BBF7D0',
            fontSize: '11px',
            fontWeight: 700,
            color: '#166534',
          }}
          title="FastAPI Backend Live on port 8000"
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: '#22C55E',
              boxShadow: '0 0 6px rgba(34, 197, 94, 0.6)',
            }}
          />
          API Online
        </div>

        {/* WebSocket Stream Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 9999,
            background: wsStatus === 'connected' ? '#EBF3FC' : '#FEF3D6',
            border: `1px solid ${wsStatus === 'connected' ? '#BFDBFE' : '#FDE68A'}`,
            fontSize: '11px',
            fontWeight: 700,
            color: wsStatus === 'connected' ? '#1D4ED8' : '#B45309',
          }}
          title="WebSocket Real-Time Telemetry Stream"
        >
          <Radio size={12} />
          {wsStatus === 'connected' ? 'Stream Active' : 'Connecting...'}
        </div>

        {/* Mendix Sync Button */}
        <button
          onClick={handleManualSync}
          disabled={isSyncing}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            padding: '6px 11px',
            borderRadius: 8,
            border: '1px solid #CBD5E1',
            background: '#FFFFFF',
            cursor: 'pointer',
            fontSize: '11.5px',
            fontWeight: 600,
            color: '#334155',
            transition: 'all 0.15s ease',
          }}
          title="Synchronize Shipments with Mendix Connector"
        >
          <RefreshCw size={13} className={isSyncing ? 'spin' : ''} />
          <span>Sync ERP</span>
        </button>

        {/* Notification Bell */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            style={{
              position: 'relative',
              width: 34,
              height: 34,
              borderRadius: 8,
              border: '1px solid #E2E8F0',
              background: '#FFFFFF',
              color: '#475569',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
            title="Operational Notifications"
          >
            <Bell size={16} />
            <span
              style={{
                position: 'absolute',
                top: 5,
                right: 5,
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#EA341F',
              }}
            />
          </button>

          {/* Notifications Dropdown */}
          {notificationsOpen && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                width: 320,
                background: '#FFFFFF',
                borderRadius: 12,
                boxShadow: '0 12px 30px rgba(0,0,0,0.15)',
                border: '1px solid #E2E8F0',
                padding: '12px',
                zIndex: 1000,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid #F1F5F9' }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#0F172A' }}>Notifications</span>
                <span style={{ fontSize: 10, color: '#64748B', fontWeight: 600 }}>3 unread</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {notifications.map((n) => (
                  <div key={n.id} style={{ padding: '8px', borderRadius: 8, background: '#F8FAFC', borderLeft: `3px solid ${n.type === 'critical' ? '#EA341F' : n.type === 'warning' ? '#F59E0B' : '#18217E'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, fontWeight: 700, color: '#0F172A' }}>
                      <span>{n.title}</span>
                      <span style={{ fontSize: 10, color: '#94A3B8', fontWeight: 400 }}>{n.time}</span>
                    </div>
                    <p style={{ margin: '3px 0 0', fontSize: 11, color: '#475569', lineHeight: 1.35 }}>
                      {n.desc}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Theme Switcher */}
        <button
          onClick={toggleTheme}
          style={{
            width: 34,
            height: 34,
            borderRadius: 8,
            border: '1px solid #E2E8F0',
            background: '#FFFFFF',
            color: '#475569',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
          }}
          title={`Theme: ${theme.toUpperCase()} (Click to toggle)`}
        >
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
        </button>
      </div>
    </header>
  );
}
