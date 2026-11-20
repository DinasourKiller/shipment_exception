import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

const AUTH_STORAGE_KEY = 'BRIDGES_AUTH_USER_v1';

export const DEMO_USERS = {
  admin: {
    id: 'USR-101',
    name: 'Bima Ary',
    email: 'admin@gmail.com',
    role: 'Administrator',
    title: 'Bridges Coordinator',
    phone: '+1 (555) 019-2834',
    avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'dashboard',
  },
  analyst: {
    id: 'USR-102',
    name: 'Sarah Lin',
    email: 'cta@gmail.com',
    role: 'Control Tower Analyst',
    title: 'Lead Operations Analyst',
    phone: '+1 (555) 019-7462',
    avatar: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'analyst_dashboard',
  },
  dispatcher: {
    id: 'USR-104',
    name: 'Elena Rostova',
    email: 'dispatcher@gmail.com',
    role: 'Dispatcher / Transport Planner',
    title: 'Highway Corridor Dispatcher',
    phone: '+1 (555) 019-9381',
    avatar: 'https://images.unsplash.com/photo-1580489944761-15a19d654956?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'dispatcher_dashboard',
  },
  carrier: {
    id: 'USR-103',
    name: 'Marcus Vance',
    email: 'carrier@gmail.com',
    role: 'Carrier Operations User',
    title: 'Carrier Fleet Dispatcher',
    carrierId: 'CAR-01',
    carrierName: 'Bridges Global Logistics',
    phone: '+1 (555) 019-5519',
    avatar: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'carrier_dashboard',
  },
  warehouse: {
    id: 'USR-105',
    name: 'Carlos Mendoza',
    email: 'warehouse@gmail.com',
    role: 'Warehouse Supervisor',
    title: 'Dallas Hub Supervisor',
    warehouseId: 'WH-DAL-01',
    warehouseName: 'Dallas Central Logistics Hub',
    phone: '+1 (555) 019-4820',
    avatar: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'warehouse_dashboard',
  },
  cs: {
    id: 'USR-106',
    name: 'Clara Hughes',
    email: 'cs@gmail.com',
    role: 'Customer Service',
    title: 'Senior Care Specialist',
    phone: '+1 (555) 019-3392',
    avatar: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'cs_dashboard',
  },
  customer: {
    id: 'USR-109',
    name: 'Sarah Jenkins',
    email: 'customer@gmail.com',
    role: 'Customer',
    title: 'Supply Chain Director',
    customerId: 'CUST-BIO-01',
    customerName: 'BioPharma Health Alliance',
    phone: '+1 (555) 019-8814',
    avatar: 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&auto=format&fit=crop&q=80',
    defaultRoute: 'customer_home',
  },
};

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem(AUTH_STORAGE_KEY);
      if (stored) return JSON.parse(stored);
    } catch (e) {
      console.warn('Failed to parse auth from localStorage:', e);
    }
    // Default to Administrator for demo readiness
    return DEMO_USERS.admin;
  });

  useEffect(() => {
    if (user) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
  }, [user]);

  const login = async (email, password) => {
    const cleanEmail = (email || '').trim().toLowerCase();
    const cleanPass = (password || '').trim();

    // Authenticate with FastAPI backend
    try {
      const res = await api.login(cleanEmail, cleanPass);
      if (!res.ok && res.status === 401) {
        return { success: false, error: 'Invalid email or password.' };
      }
    } catch (e) {
      console.warn('Backend login attempt had issue:', e);
    }

    // Match to demo user profile
    let matched = null;
    if (cleanEmail === 'admin@gmail.com' || cleanEmail === 'admin@controltower.corp') {
      matched = DEMO_USERS.admin;
    } else if (cleanEmail === 'cta@gmail.com' || cleanEmail === 'analyst@gmail.com' || cleanEmail === 'analyst@controltower.corp') {
      matched = DEMO_USERS.analyst;
    } else if (cleanEmail === 'dispatcher@gmail.com' || cleanEmail === 'dispatcher@controltower.corp') {
      matched = DEMO_USERS.dispatcher;
    } else if (cleanEmail === 'carrier@gmail.com' || cleanEmail === 'carrier@controltower.corp') {
      matched = DEMO_USERS.carrier;
    } else if (cleanEmail === 'warehouse@gmail.com' || cleanEmail === 'manager@controltower.corp') {
      matched = DEMO_USERS.warehouse;
    } else if (cleanEmail === 'cs@gmail.com') {
      matched = DEMO_USERS.cs;
    } else if (cleanEmail === 'customer@gmail.com') {
      matched = DEMO_USERS.customer;
    } else {
      matched = {
        id: 'USR-' + Math.floor(Math.random() * 900 + 100),
        name: cleanEmail.split('@')[0],
        email: cleanEmail,
        role: 'Administrator',
        title: 'Platform Operator',
        phone: '+1 (555) 019-0000',
        avatar: DEMO_USERS.admin.avatar,
        defaultRoute: 'dashboard',
      };
    }

    setUser(matched);
    return { success: true, user: matched };
  };

  const logout = async () => {
    await api.logout();
    setUser(null);
  };

  const switchRole = (roleKeyOrName) => {
    let target = null;
    if (DEMO_USERS[roleKeyOrName]) {
      target = DEMO_USERS[roleKeyOrName];
    } else {
      target = Object.values(DEMO_USERS).find(
        (u) => u.role.toLowerCase() === roleKeyOrName.toLowerCase()
      );
    }

    if (target) {
      setUser(target);
      // Auto authenticate to backend for that role
      api.login(target.email, '1').catch(() => {});
      return target;
    }
    return user;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role || 'Guest',
        isAuthenticated: !!user,
        login,
        logout,
        switchRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
