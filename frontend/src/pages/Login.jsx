import React, { useState } from 'react';
import { useAuth, DEMO_USERS } from '../context/AuthContext';

const DEMO_ROLES = [
  { key: 'admin', label: 'Admin', email: DEMO_USERS.admin?.email || 'admin@gmail.com' },
  { key: 'analyst', label: 'Analyst', email: DEMO_USERS.analyst?.email || 'cta@gmail.com' },
  { key: 'dispatcher', label: 'Dispatcher', email: DEMO_USERS.dispatcher?.email || 'dispatcher@gmail.com' },
  { key: 'carrier', label: 'Carrier', email: DEMO_USERS.carrier?.email || 'carrier@gmail.com' },
  { key: 'warehouse', label: 'Warehouse', email: DEMO_USERS.warehouse?.email || 'warehouse@gmail.com' },
  { key: 'cs', label: 'Cust Serv', email: DEMO_USERS.cs?.email || 'cs@gmail.com', isCustServ: true },
  { key: 'customer', label: 'Customer', email: DEMO_USERS.customer?.email || 'customer@gmail.com' },
];

export default function Login({ onLoginSuccess }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('dispatcher@gmail.com');
  const [password, setPassword] = useState('1');
  const [selectedRole, setSelectedRole] = useState('customer');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await login(email, password);
      if (result.success) {
        if (onLoginSuccess) onLoginSuccess(result.user?.defaultRoute || 'dashboard');
      } else {
        setError(result.error || 'Authentication failed. Please check credentials.');
      }
    } catch (err) {
      setError(err.message || 'An error occurred during authentication.');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRole = (roleItem) => {
    setSelectedRole(roleItem.key);
    setEmail(roleItem.email);
    setPassword('1');
    setError('');
  };

  const handleEmailChange = (val) => {
    setEmail(val);
    const match = DEMO_ROLES.find((r) => r.email.toLowerCase() === val.toLowerCase().trim());
    setSelectedRole(match ? match.key : null);
  };

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        minHeight: '480px',
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
        paddingRight: 'max(110px, 12.5vw)',
      }}
    >
      {/* Right Column: Form Area - Exactly matched to mockup proportions */}
      <div
        style={{
          width: '240px',
          boxSizing: 'border-box',
          position: 'relative',
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <h1
          style={{
            fontSize: '22px',
            fontWeight: 700,
            color: '#0F172A',
            margin: '0 0 4px 0',
            letterSpacing: '-0.3px',
            lineHeight: 1.2,
          }}
        >
          Login
        </h1>

        <p
          style={{
            fontSize: '11px',
            color: '#64748B',
            margin: '0 0 18px 0',
            fontWeight: 400,
            lineHeight: 1.35,
          }}
        >
          Welcome to Shipment exception control management
        </p>

        {error && (
          <div
            style={{
              padding: '6px 10px',
              borderRadius: '4px',
              background: '#FEF2F2',
              border: '1px solid #FCA5A5',
              color: '#B91C1C',
              fontSize: '10.5px',
              fontWeight: 500,
              marginBottom: '12px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column' }}>
          {/* E-mail input */}
          <div style={{ marginBottom: '12px' }}>
            <label
              htmlFor="login-email"
              style={{
                display: 'block',
                fontSize: '11px',
                fontWeight: 500,
                color: '#475569',
                marginBottom: '4px',
              }}
            >
              E-mail
            </label>
            <input
              id="login-email"
              type="email"
              required
              value={email}
              onChange={(e) => handleEmailChange(e.target.value)}
              placeholder="name@company.com"
              style={{
                width: '100%',
                height: '30px',
                padding: '0 10px',
                borderRadius: '6px',
                backgroundColor: '#F1F4F9',
                border: '1px solid transparent',
                fontSize: '11.5px',
                color: '#0F172A',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'all 0.15s ease',
              }}
              onFocus={(e) => {
                e.target.style.backgroundColor = '#FFFFFF';
                e.target.style.borderColor = '#0D5CE5';
                e.target.style.boxShadow = '0 0 0 2px rgba(13, 92, 229, 0.12)';
              }}
              onBlur={(e) => {
                e.target.style.backgroundColor = '#F1F4F9';
                e.target.style.borderColor = 'transparent';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Password input */}
          <div style={{ marginBottom: '16px' }}>
            <label
              htmlFor="login-password"
              style={{
                display: 'block',
                fontSize: '11px',
                fontWeight: 500,
                color: '#475569',
                marginBottom: '4px',
              }}
            >
              Password
            </label>
            <input
              id="login-password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{
                width: '100%',
                height: '30px',
                padding: '0 10px',
                borderRadius: '6px',
                backgroundColor: '#F1F4F9',
                border: '1px solid transparent',
                fontSize: '11.5px',
                color: '#0F172A',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'all 0.15s ease',
              }}
              onFocus={(e) => {
                e.target.style.backgroundColor = '#FFFFFF';
                e.target.style.borderColor = '#0D5CE5';
                e.target.style.boxShadow = '0 0 0 2px rgba(13, 92, 229, 0.12)';
              }}
              onBlur={(e) => {
                e.target.style.backgroundColor = '#F1F4F9';
                e.target.style.borderColor = 'transparent';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Primary Login Button */}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              height: '30px',
              borderRadius: '6px',
              backgroundColor: '#0D5CE5',
              color: '#FFFFFF',
              border: 'none',
              fontSize: '12px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 4px rgba(13, 92, 229, 0.2)',
              transition: 'background-color 0.15s ease',
              opacity: loading ? 0.7 : 1,
            }}
            onMouseEnter={(e) => {
              if (!loading) e.currentTarget.style.backgroundColor = '#0B4DC4';
            }}
            onMouseLeave={(e) => {
              if (!loading) e.currentTarget.style.backgroundColor = '#0D5CE5';
            }}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        {/* Demo Access Roles Card */}
        <div
          style={{
            marginTop: '14px',
            border: '1px solid #E2E8F0',
            borderRadius: '6px',
            padding: '6px 7px 7px 7px',
            backgroundColor: '#FFFFFF',
            boxSizing: 'border-box',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '5px',
            }}
          >
            <span style={{ fontSize: '9.5px', fontWeight: 700, color: '#0F172A' }}>
              Demo Access Roles:
            </span>
            <span style={{ fontSize: '9px', color: '#64748B', fontWeight: 400 }}>
              password: 1
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gap: '2px',
              alignItems: 'stretch',
            }}
          >
            {DEMO_ROLES.map((role) => {
              const isSelected = selectedRole === role.key;
              return (
                <button
                  key={role.key}
                  type="button"
                  onClick={() => handleSelectRole(role)}
                  style={{
                    height: '21px',
                    padding: '0 1px',
                    border: isSelected ? '1px solid #18217E' : '1px solid #CBD5E1',
                    borderRadius: '3px',
                    backgroundColor: isSelected ? '#18217E' : '#FFFFFF',
                    color: isSelected ? '#FFFFFF' : (role.isCustServ ? '#991B1B' : '#1E293B'),
                    fontSize: '8.5px',
                    fontWeight: isSelected ? 700 : 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    lineHeight: '1.0',
                    transition: 'all 0.15s ease',
                  }}
                  title={`Login as ${role.label} (${role.email})`}
                >
                  {role.isCustServ ? (
                    <span style={{ fontSize: '7.5px', lineHeight: '1.0' }}>
                      Cust
                      <br />
                      Serv
                    </span>
                  ) : (
                    role.label
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
