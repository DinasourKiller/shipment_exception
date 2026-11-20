import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';
import Sidebar from './components/layout/Sidebar';
import Header from './components/layout/Header';
import Login from './pages/Login';
import DashboardView from './pages/DashboardView';
import ShipmentsView from './pages/ShipmentsView';
import ExceptionsView from './pages/ExceptionsView';
import InvestigationView from './pages/InvestigationView';
import WarRoomView from './pages/WarRoomView';
import RecoveryView from './pages/RecoveryView';
import ClaimsView from './pages/ClaimsView';
import GeofencesView from './pages/GeofencesView';
import DeliveryView from './pages/DeliveryView';
import CarriersView from './pages/CarriersView';
import UsersView from './pages/UsersView';
import AnalyticsView from './pages/AnalyticsView';
import AuditView from './pages/AuditView';
import DiagnosticsView from './pages/DiagnosticsView';
import WarehouseView from './pages/WarehouseView';
import CustomerPortalView from './pages/CustomerPortalView';

function AppContent() {
  const { isAuthenticated, user } = useAuth();
  const [currentView, setCurrentView] = useState('dashboard');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

  useEffect(() => {
    if (user?.defaultRoute) {
      setCurrentView(user.defaultRoute);
    }
  }, [user]);

  if (!isAuthenticated) {
    return <Login onLoginSuccess={(route) => setCurrentView(route || 'dashboard')} />;
  }

  const renderActiveView = () => {
    switch (currentView) {
      case 'dashboard':
      case 'analyst_dashboard':
      case 'dispatcher_dashboard':
        return <DashboardView onNavigate={setCurrentView} />;
      case 'shipments':
        return <ShipmentsView onNavigate={setCurrentView} />;
      case 'exceptions':
        return <ExceptionsView onNavigate={setCurrentView} />;
      case 'investigation':
        return <InvestigationView onNavigate={setCurrentView} />;
      case 'war_room':
        return <WarRoomView onNavigate={setCurrentView} />;
      case 'recovery':
      case 'carrier_dashboard':
        return <RecoveryView onNavigate={setCurrentView} />;
      case 'claims':
        return <ClaimsView onNavigate={setCurrentView} />;
      case 'geofences':
        return <GeofencesView onNavigate={setCurrentView} />;
      case 'delivery':
        return <DeliveryView onNavigate={setCurrentView} />;
      case 'carriers':
        return <CarriersView onNavigate={setCurrentView} />;
      case 'users':
        return <UsersView onNavigate={setCurrentView} />;
      case 'analytics':
        return <AnalyticsView onNavigate={setCurrentView} />;
      case 'audit':
        return <AuditView onNavigate={setCurrentView} />;
      case 'diagnostics':
        return <DiagnosticsView onNavigate={setCurrentView} />;
      case 'warehouse':
      case 'warehouse_dashboard':
        return <WarehouseView onNavigate={setCurrentView} />;
      case 'customer_home':
      case 'cs_dashboard':
      case 'ai_copilot':
        return <CustomerPortalView onNavigate={setCurrentView} />;
      default:
        return <DashboardView onNavigate={setCurrentView} />;
    }
  };

  return (
    <div className={`app-layout ${isSidebarCollapsed ? 'sidebar-is-collapsed' : ''}`} style={{ height: '100vh', width: '100vw', display: 'flex', overflow: 'hidden' }}>
      <Sidebar
        currentView={currentView}
        onNavigate={setCurrentView}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />
      <div className="app-main-wrapper" style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <Header currentView={currentView} onNavigate={setCurrentView} />
        <main className="page-content" style={{ flex: 1, overflowY: 'auto', background: 'var(--color-bg-page, #F8F9FA)' }}>
          {renderActiveView()}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <AppContent />
      </ToastProvider>
    </AuthProvider>
  );
}
