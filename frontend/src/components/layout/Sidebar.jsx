import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  LayoutDashboard,
  Package,
  AlertTriangle,
  FileText,
  MapPin,
  Truck,
  Users,
  BarChart3,
  ShieldCheck,
  Activity,
  Search,
  Flame,
  RefreshCw,
  Navigation,
  CheckCircle,
  AlertOctagon,
  Home,
  Thermometer,
  Bot,
  LogOut,
  ChevronUp,
  Layers,
} from 'lucide-react';

export default function Sidebar({ currentView, onNavigate, isCollapsed, onToggleCollapse }) {
  const { user, role, switchRole, logout } = useAuth();
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);

  // Define role-specific navigation menus
  const getNavItems = () => {
    switch (role) {
      case 'Control Tower Analyst':
        return [
          { id: 'analyst_dashboard', label: 'Analyst Overview', icon: LayoutDashboard },
          { id: 'shipments', label: 'Active Shipments', icon: Package },
          { id: 'exceptions', label: 'Exception Queue', icon: AlertTriangle, badge: '5', badgeColor: '#EA341F' },
          { id: 'investigation', label: 'Investigation Workspace', icon: Search },
          { id: 'war_room', label: 'War Room Command', icon: Flame, badge: 'LIVE', badgeColor: '#EA341F' },
          { id: 'recovery', label: 'Recovery Requests', icon: RefreshCw },
          { id: 'geofences', label: 'Geofence Corridors', icon: MapPin },
          { id: 'claims', label: 'Claims Ledger', icon: FileText },
        ];
      case 'Dispatcher / Transport Planner':
        return [
          { id: 'dispatcher_dashboard', label: 'Dispatcher Hub', icon: LayoutDashboard },
          { id: 'shipments', label: 'Corridor Shipments', icon: Package },
          { id: 'exceptions', label: 'Triage Queue', icon: AlertTriangle, badge: '3', badgeColor: '#B45309' },
          { id: 'recovery', label: 'Carrier Recovery Tenders', icon: RefreshCw },
          { id: 'geofences', label: 'Corridor & Geofences', icon: MapPin },
          { id: 'tracking', label: 'Live Highway Map', icon: Navigation },
        ];
      case 'Carrier Operations User':
        return [
          { id: 'carrier_dashboard', label: 'Carrier Hub (CAR-01)', icon: LayoutDashboard },
          { id: 'recovery', label: 'Recovery Tenders', icon: RefreshCw, badge: '1 Action', badgeColor: '#10B981' },
          { id: 'shipments', label: 'Assigned Shipments', icon: Package },
          { id: 'delivery', label: 'Delivery & ePOD', icon: CheckCircle },
          { id: 'exceptions', label: 'Report Disruption', icon: AlertOctagon },
        ];
      case 'Warehouse Supervisor':
        return [
          { id: 'warehouse_dashboard', label: 'Warehouse Hub', icon: LayoutDashboard },
          { id: 'warehouse', label: 'Dock Bays & Staging', icon: Home },
          { id: 'shipments', label: 'Inbound / Outbound', icon: Package },
          { id: 'delivery', label: 'Security Gate Handover', icon: CheckCircle },
          { id: 'exceptions', label: 'Dock Exceptions', icon: AlertTriangle },
        ];
      case 'Customer Service':
        return [
          { id: 'cs_dashboard', label: 'CS Overview', icon: LayoutDashboard },
          { id: 'shipments', label: 'Monitored Accounts', icon: Package },
          { id: 'exceptions', label: 'Customer Queue', icon: AlertTriangle },
          { id: 'ai_copilot', label: 'CS AI Copilot', icon: Bot },
        ];
      case 'Customer':
        return [
          { id: 'customer_home', label: 'Shipper Home', icon: LayoutDashboard },
          { id: 'shipments', label: 'Track My Orders', icon: Search },
          { id: 'ai_copilot', label: '24/7 AI Assistant', icon: Bot },
        ];
      case 'Administrator':
      default:
        return [
          { id: 'dashboard', label: 'Control Tower', icon: LayoutDashboard },
          { id: 'shipments', label: 'Shipments Ledger', icon: Package },
          { id: 'exceptions', label: 'Exceptions & SLA', icon: AlertTriangle, badge: '5', badgeColor: '#EA341F' },
          { id: 'recovery', label: 'Carrier Recovery', icon: RefreshCw },
          { id: 'claims', label: 'Claims & Settlement', icon: FileText, badge: 'SLA', badgeColor: '#424989' },
          { id: 'geofences', label: 'Geofences & Dwell', icon: MapPin },
          { id: 'delivery', label: 'e-POD Delivery', icon: CheckCircle },
          { id: 'carriers', label: 'Carrier Network', icon: Truck },
          { id: 'users', label: 'Users & RBAC', icon: Users },
          { id: 'analytics', label: 'Analytics & KPIs', icon: BarChart3 },
          { id: 'audit', label: 'Cryptographic Audit', icon: ShieldCheck },
          { id: 'diagnostics', label: 'System Health', icon: Activity, badge: '100%', badgeColor: '#10B981' },
        ];
    }
  };

  const navItems = getNavItems();

  const handleRoleSelect = (roleKey) => {
    const updated = switchRole(roleKey);
    setProfileDropdownOpen(false);
    if (updated?.defaultRoute) {
      onNavigate(updated.defaultRoute);
    }
  };

  return (
    <aside className="app-sidebar" style={{ width: isCollapsed ? 68 : 236, minWidth: isCollapsed ? 68 : 236 }}>
      {/* Brand Top Header */}
      <div className="sidebar-top">
        <div className="sidebar-brand" onClick={() => onNavigate(user?.defaultRoute || 'dashboard')}>
          <div className="brand-logo-icon">
            <Layers size={18} color="#FFFFFF" />
          </div>
          {!isCollapsed && <span className="brand-name">BRIDGES</span>}
        </div>
        <button className="sidebar-collapse-btn" onClick={onToggleCollapse} title="Toggle Sidebar">
          {isCollapsed ? '→' : '←'}
        </button>
      </div>

      {/* Navigation Menu */}
      <nav className="sidebar-nav">
        <ul className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.id;
            return (
              <li key={item.id}>
                <div
                  className={`nav-link ${isActive ? 'active' : ''}`}
                  onClick={() => onNavigate(item.id)}
                  title={item.label}
                >
                  <div className="nav-link-left">
                    <span className="nav-icon">
                      <Icon size={17} />
                    </span>
                    {!isCollapsed && <span className="nav-label">{item.label}</span>}
                  </div>
                  {!isCollapsed && item.badge && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: 9999,
                        background: item.badgeColor || '#18217E',
                        color: '#FFFFFF',
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Role Switcher Popover */}
      {profileDropdownOpen && !isCollapsed && (
        <div
          style={{
            position: 'absolute',
            bottom: 70,
            left: 12,
            width: 212,
            background: '#FFFFFF',
            borderRadius: 10,
            boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            border: '1px solid #E2E8F0',
            padding: '8px 0',
            zIndex: 100,
          }}
        >
          <div style={{ padding: '4px 12px 8px', borderBottom: '1px solid #F1F5F9', fontSize: 10, fontWeight: 700, color: '#64748B', textTransform: 'uppercase' }}>
            Switch Role Workspace
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Administrator' ? '#EEF2FF' : 'transparent', color: role === 'Administrator' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('admin')}
          >
            🛡️ Administrator
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Control Tower Analyst' ? '#EEF2FF' : 'transparent', color: role === 'Control Tower Analyst' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('analyst')}
          >
            🔬 Control Tower Analyst
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Dispatcher / Transport Planner' ? '#EEF2FF' : 'transparent', color: role === 'Dispatcher / Transport Planner' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('dispatcher')}
          >
            🚚 Dispatcher / Planner
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Carrier Operations User' ? '#EEF2FF' : 'transparent', color: role === 'Carrier Operations User' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('carrier')}
          >
            🚛 Carrier Operations (CAR-01)
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Warehouse Supervisor' ? '#EEF2FF' : 'transparent', color: role === 'Warehouse Supervisor' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('warehouse')}
          >
            🏭 Warehouse (Dallas Hub)
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Customer Service' ? '#EEF2FF' : 'transparent', color: role === 'Customer Service' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('cs')}
          >
            🎧 Customer Service
          </div>
          <div
            style={{ padding: '6px 12px', fontSize: 12, cursor: 'pointer', background: role === 'Customer' ? '#EEF2FF' : 'transparent', color: role === 'Customer' ? '#18217E' : '#334155', fontWeight: 600 }}
            onClick={() => handleRoleSelect('customer')}
          >
            🏢 Shipper / Customer
          </div>
        </div>
      )}

      {/* Sidebar Footer: Profile Card */}
      <div className="sidebar-footer">
        <div
          className="user-profile-card"
          onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
          title="Click to Switch Role Workspace"
        >
          <div className="profile-avatar-wrap">
            <img src={user?.avatar} alt={user?.name} className="profile-avatar-img" />
          </div>
          {!isCollapsed && (
            <>
              <div className="profile-info-wrap">
                <span className="profile-name">{user?.name}</span>
                <span className="profile-sub">{user?.title || role}</span>
              </div>
              <ChevronUp size={14} className="profile-chevron" />
            </>
          )}
          <button
            className="profile-logout-icon-btn"
            onClick={(e) => {
              e.stopPropagation();
              logout();
            }}
            title="Log Out"
          >
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </aside>
  );
}
