import React, { useState } from 'react';
import { useAuth, DEMO_USERS } from '../context/AuthContext';
import {
  Lock,
  Mail,
  User,
  Shield,
  ArrowRight,
  Eye,
  EyeOff,
  UserPlus,
  LogIn,
  CheckCircle2,
  Building,
} from 'lucide-react';

const ENTERPRISE_ROLES = [
  {
    id: 'dispatcher',
    name: 'Dispatcher / Transport Planner',
    description: 'Fleet routing, live corridor deviations & tender dispatching',
    defaultEmail: 'dispatcher@gmail.com',
  },
  {
    id: 'analyst',
    name: 'Control Tower Analyst',
    description: 'Thermal breach triage, SLA forensic root cause & telemetry',
    defaultEmail: 'cta@gmail.com',
  },
  {
    id: 'admin',
    name: 'System Administrator',
    description: 'Full workspace governance, cryptographic audit trails & RBAC',
    defaultEmail: 'admin@gmail.com',
  },
  {
    id: 'carrier',
    name: 'Carrier Operations User',
    description: 'Tender bidding, driver telematics & electronic POD handover',
    defaultEmail: 'carrier@gmail.com',
  },
  {
    id: 'warehouse',
    name: 'Warehouse Supervisor',
    description: 'Dock door assignments, cross-dock dwell & hub capacity',
    defaultEmail: 'warehouse@gmail.com',
  },
  {
    id: 'cs',
    name: 'Customer Service Specialist',
    description: 'Consignment inquiry tickets, proactive SLA claims & care',
    defaultEmail: 'cs@gmail.com',
  },
  {
    id: 'customer',
    name: 'Shipper / Enterprise Customer',
    description: 'Multi-modal shipment tracking, deviation alerts & self-service',
    defaultEmail: 'customer@gmail.com',
  },
];

export default function Login({ onLoginSuccess }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [showPassword, setShowPassword] = useState(false);

  // Login form state
  const [loginEmail, setLoginEmail] = useState('dispatcher@gmail.com');
  const [loginPassword, setLoginPassword] = useState('1');
  const [rememberMe, setRememberMe] = useState(true);

  // Registration / Role creation state
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regRole, setRegRole] = useState(ENTERPRISE_ROLES[0].name);
  const [regPassword, setRegPassword] = useState('Password123!');
  const [regConfirmPassword, setRegConfirmPassword] = useState('Password123!');
  const [regOrg, setRegOrg] = useState('Global Logistics Hub');

  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [loading, setLoading] = useState(false);

  // Handle Login submission
  const handleLoginSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');
    setLoading(true);

    try {
      const result = await login(loginEmail, loginPassword);
      if (result.success) {
        if (onLoginSuccess) {
          onLoginSuccess(result.user?.defaultRoute || 'dashboard');
        }
      } else {
        setError(result.error || 'Invalid credentials. Please verify your email and password.');
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check network connection.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Registration / Role creation submission
  const handleRegisterSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    if (regPassword !== regConfirmPassword) {
      setError('Passwords do not match. Please verify both password fields.');
      return;
    }
    if (regPassword.length < 1) {
      setError('Please provide a secure password.');
      return;
    }

    setLoading(true);
    try {
      const result = await register({
        name: regName,
        email: regEmail,
        password: regPassword,
        role: regRole,
        organization: regOrg,
      });

      if (result.success) {
        setSuccessMsg(`Role account created for ${result.user.name} (${result.user.role}).`);
        setTimeout(() => {
          if (onLoginSuccess) {
            onLoginSuccess(result.user?.defaultRoute || 'dashboard');
          }
        }, 600);
      } else {
        setError(result.error || 'Failed to create role account.');
      }
    } catch (err) {
      setError(err.message || 'Error occurred while creating user account.');
    } finally {
      setLoading(false);
    }
  };

  // Quick preset helper to quickly populate standard credentials for testing
  const handlePresetSelect = (roleItem) => {
    setLoginEmail(roleItem.defaultEmail);
    setLoginPassword('1');
    setError('');
  };

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        minHeight: '600px',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'flex-end',
        backgroundColor: '#FFFFFF',
        backgroundImage: "url('/assets/login-exception-tower.jpg')",
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'left center',
        backgroundSize: 'cover',
        fontFamily: '"Plus Jakarta Sans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        overflow: 'hidden',
        boxSizing: 'border-box',
        paddingRight: 'max(48px, 7vw)',
      }}
    >
      {/* Enterprise Authentication Card */}
      <div
        style={{
          width: '100%',
          maxWidth: '390px',
          backgroundColor: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(20px)',
          borderRadius: '16px',
          border: '1px solid #E2E8F0',
          boxShadow: '0 20px 45px -12px rgba(15, 23, 42, 0.1), 0 1px 3px rgba(15, 23, 42, 0.05)',
          padding: '28px 28px',
          boxSizing: 'border-box',
          position: 'relative',
          zIndex: 10,
        }}
      >
        {/* Mode Switcher Tabs */}
        <div
          style={{
            display: 'flex',
            backgroundColor: '#F1F5F9',
            borderRadius: '8px',
            padding: '3px',
            marginBottom: '20px',
          }}
        >
          <button
            type="button"
            onClick={() => {
              setMode('login');
              setError('');
              setSuccessMsg('');
            }}
            style={{
              flex: 1,
              height: '32px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: mode === 'login' ? '#FFFFFF' : 'transparent',
              color: mode === 'login' ? '#0F172A' : '#64748B',
              fontSize: '12.5px',
              fontWeight: mode === 'login' ? 700 : 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: mode === 'login' ? '0 1px 3px rgba(0, 0, 0, 0.08)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <LogIn size={14} />
            <span>Sign In</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setMode('register');
              setError('');
              setSuccessMsg('');
            }}
            style={{
              flex: 1,
              height: '32px',
              border: 'none',
              borderRadius: '6px',
              backgroundColor: mode === 'register' ? '#FFFFFF' : 'transparent',
              color: mode === 'register' ? '#0F172A' : '#64748B',
              fontSize: '12.5px',
              fontWeight: mode === 'register' ? 700 : 500,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              boxShadow: mode === 'register' ? '0 1px 3px rgba(0, 0, 0, 0.08)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            <UserPlus size={14} />
            <span>Create Account</span>
          </button>
        </div>

        {/* Heading & Subtitle */}
        <div style={{ marginBottom: '18px' }}>
          <h1
            style={{
              fontSize: '24px',
              fontWeight: 800,
              color: '#0F172A',
              margin: '0 0 4px 0',
              letterSpacing: '-0.3px',
            }}
          >
            {mode === 'login' ? 'Login' : 'Create Role Account'}
          </h1>
          <p
            style={{
              fontSize: '12.5px',
              color: '#64748B',
              margin: 0,
              lineHeight: 1.4,
            }}
          >
            {mode === 'login'
              ? 'Welcome to Shipment exception control management'
              : 'Select your operational role and configure credentials'}
          </p>
        </div>

        {/* Feedback Alerts */}
        {error && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#FEF2F2',
              border: '1px solid #FCA5A5',
              color: '#B91C1C',
              fontSize: '11.5px',
              fontWeight: 500,
              marginBottom: '14px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              backgroundColor: '#ECFDF5',
              border: '1px solid #6EE7B7',
              color: '#065F46',
              fontSize: '11.5px',
              fontWeight: 600,
              marginBottom: '14px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <CheckCircle2 size={14} />
            <span>{successMsg}</span>
          </div>
        )}

        {/* MODE: SIGN IN */}
        {mode === 'login' && (
          <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label
                htmlFor="signin-email"
                style={{
                  display: 'block',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#334155',
                  marginBottom: '5px',
                }}
              >
                Work Email Address
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: '12px', color: '#94A3B8' }}>
                  <Mail size={15} />
                </span>
                <input
                  id="signin-email"
                  type="email"
                  required
                  value={loginEmail}
                  onChange={(e) => setLoginEmail(e.target.value)}
                  placeholder="name@company.com"
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '0 12px 0 36px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'all 0.15s ease',
                  }}
                  onFocus={(e) => {
                    e.target.style.backgroundColor = '#FFFFFF';
                    e.target.style.borderColor = '#0D5CE5';
                    e.target.style.boxShadow = '0 0 0 3px rgba(13, 92, 229, 0.12)';
                  }}
                  onBlur={(e) => {
                    e.target.style.backgroundColor = '#F8FAFC';
                    e.target.style.borderColor = '#CBD5E1';
                    e.target.style.boxShadow = 'none';
                  }}
                />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '5px' }}>
                <label
                  htmlFor="signin-password"
                  style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    color: '#334155',
                  }}
                >
                  Password
                </label>
                <button
                  type="button"
                  onClick={() => alert("Standard demo accounts share password: '1' or 'Password123!'")}
                  style={{
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    fontSize: '11px',
                    color: '#0D5CE5',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Forgot?
                </button>
              </div>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: '12px', color: '#94A3B8' }}>
                  <Lock size={15} />
                </span>
                <input
                  id="signin-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{
                    width: '100%',
                    height: '38px',
                    padding: '0 36px 0 36px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '13px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                    transition: 'all 0.15s ease',
                  }}
                  onFocus={(e) => {
                    e.target.style.backgroundColor = '#FFFFFF';
                    e.target.style.borderColor = '#0D5CE5';
                    e.target.style.boxShadow = '0 0 0 3px rgba(13, 92, 229, 0.12)';
                  }}
                  onBlur={(e) => {
                    e.target.style.backgroundColor = '#F8FAFC';
                    e.target.style.borderColor = '#CBD5E1';
                    e.target.style.boxShadow = 'none';
                  }}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={{
                    position: 'absolute',
                    right: '10px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: '#94A3B8',
                    padding: '4px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '-2px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11.5px', color: '#64748B', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  style={{ accentColor: '#0D5CE5', cursor: 'pointer' }}
                />
                <span>Remember this device</span>
              </label>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                height: '40px',
                borderRadius: '8px',
                backgroundColor: '#0D5CE5',
                color: '#FFFFFF',
                border: 'none',
                fontSize: '13.5px',
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 4px 12px rgba(13, 92, 229, 0.25)',
                transition: 'all 0.15s ease',
                marginTop: '4px',
              }}
              onMouseEnter={(e) => {
                if (!loading) e.currentTarget.style.backgroundColor = '#0B4DC4';
              }}
              onMouseLeave={(e) => {
                if (!loading) e.currentTarget.style.backgroundColor = '#0D5CE5';
              }}
            >
              <span>{loading ? 'Authenticating...' : 'Sign In to Workspace'}</span>
              <ArrowRight size={15} />
            </button>

            {/* Quick role autofill helper */}
            <div style={{ marginTop: '10px', paddingTop: '12px', borderTop: '1px solid #F1F5F9' }}>
              <div style={{ fontSize: '11px', color: '#64748B', marginBottom: '6px', display: 'flex', justifyContent: 'space-between' }}>
                <span>Quick Fill Preset Role:</span>
                <span style={{ color: '#94A3B8' }}>password: 1</span>
              </div>
              <select
                onChange={(e) => {
                  const found = ENTERPRISE_ROLES.find((r) => r.id === e.target.value);
                  if (found) handlePresetSelect(found);
                }}
                defaultValue="dispatcher"
                style={{
                  width: '100%',
                  height: '32px',
                  borderRadius: '6px',
                  border: '1px solid #E2E8F0',
                  backgroundColor: '#F8FAFC',
                  fontSize: '11.5px',
                  color: '#334155',
                  padding: '0 8px',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                {ENTERPRISE_ROLES.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.defaultEmail})
                  </option>
                ))}
              </select>
            </div>
          </form>
        )}

        {/* MODE: CREATE ACCOUNT / ROLE CREATION */}
        {mode === 'register' && (
          <form onSubmit={handleRegisterSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label
                htmlFor="reg-name"
                style={{ display: 'block', fontSize: '11.5px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}
              >
                Full Name
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: '12px', color: '#94A3B8' }}>
                  <User size={14} />
                </span>
                <input
                  id="reg-name"
                  type="text"
                  required
                  value={regName}
                  onChange={(e) => setRegName(e.target.value)}
                  placeholder="e.g. Elena Rostova"
                  style={{
                    width: '100%',
                    height: '36px',
                    padding: '0 12px 0 34px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '12.5px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="reg-email"
                style={{ display: 'block', fontSize: '11.5px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}
              >
                Corporate Email Address
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: '12px', color: '#94A3B8' }}>
                  <Mail size={14} />
                </span>
                <input
                  id="reg-email"
                  type="email"
                  required
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  placeholder="e.g. elena@controltower.corp"
                  style={{
                    width: '100%',
                    height: '36px',
                    padding: '0 12px 0 34px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '12.5px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="reg-role"
                style={{ display: 'block', fontSize: '11.5px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}
              >
                Assign Operational Role
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: '12px', color: '#94A3B8' }}>
                  <Shield size={14} />
                </span>
                <select
                  id="reg-role"
                  value={regRole}
                  onChange={(e) => setRegRole(e.target.value)}
                  style={{
                    width: '100%',
                    height: '36px',
                    padding: '0 12px 0 34px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '12.5px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                    cursor: 'pointer',
                  }}
                >
                  {ENTERPRISE_ROLES.map((r) => (
                    <option key={r.id} value={r.name}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
              <div style={{ fontSize: '10.5px', color: '#64748B', marginTop: '3px' }}>
                {ENTERPRISE_ROLES.find((r) => r.name === regRole)?.description}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div>
                <label
                  htmlFor="reg-pass"
                  style={{ display: 'block', fontSize: '11.5px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}
                >
                  Password
                </label>
                <input
                  id="reg-pass"
                  type="password"
                  required
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{
                    width: '100%',
                    height: '36px',
                    padding: '0 10px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '12.5px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label
                  htmlFor="reg-confirm"
                  style={{ display: 'block', fontSize: '11.5px', fontWeight: 600, color: '#334155', marginBottom: '4px' }}
                >
                  Confirm Password
                </label>
                <input
                  id="reg-confirm"
                  type="password"
                  required
                  value={regConfirmPassword}
                  onChange={(e) => setRegConfirmPassword(e.target.value)}
                  placeholder="••••••••"
                  style={{
                    width: '100%',
                    height: '36px',
                    padding: '0 10px',
                    borderRadius: '8px',
                    backgroundColor: '#F8FAFC',
                    border: '1px solid #CBD5E1',
                    fontSize: '12.5px',
                    color: '#0F172A',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                width: '100%',
                height: '40px',
                borderRadius: '8px',
                backgroundColor: '#0D5CE5',
                color: '#FFFFFF',
                border: 'none',
                fontSize: '13.5px',
                fontWeight: 700,
                cursor: loading ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                boxShadow: '0 4px 12px rgba(13, 92, 229, 0.25)',
                transition: 'all 0.15s ease',
                marginTop: '6px',
              }}
            >
              <span>{loading ? 'Creating Role Account...' : 'Create Role Account & Launch'}</span>
              <ArrowRight size={15} />
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
