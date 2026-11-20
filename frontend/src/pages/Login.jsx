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
        paddingRight: 'min(12vw, 140px)',
      }}
    >
      {/* Right Column: Form Area */}
      <div
        style={{
          width: '100%',
          maxWidth: '380px',
          boxSizing: 'border-box',
          position: 'relative',
          zIndex: 10,
          padding: '24px 8px',
        }}
      >
        <h1
          style={{
            fontSize: '32px',
            fontWeight: 700,
            color: '#0F172A',
            margin: '0 0 6px 0',
            letterSpacing: '-0.4px',
          }}
        >
          Login
        </h1>

        <p
          style={{
            fontSize: '13px',
            color: '#64748B',
            margin: '0 0 24px 0',
            fontWeight: 400,
          }}
        >
          Welcome to Shipment exception control management
        </p>

        {error && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '6px',
              background: '#FEF2F2',
              border: '1px solid #FCA5A5',
              color: '#B91C1C',
              fontSize: '12px',
              fontWeight: 500,
              marginBottom: '16px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column' }}>
          {/* E-mail input */}
          <div style={{ marginBottom: '16px' }}>
            <label
              htmlFor="login-email"
              style={{
                display: 'block',
                fontSize: '12.5px',
                fontWeight: 500,
                color: '#475569',
                marginBottom: '6px',
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
                height: '42px',
                padding: '0 14px',
                borderRadius: '6px',
                backgroundColor: '#F1F4F9',
                border: '1px solid transparent',
                fontSize: '13.5px',
                color: '#0F172A',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'all 0.15s ease',
              }}
              onFocus={(e) => {
                e.target.style.backgroundColor = '#FFFFFF';
                e.target.style.borderColor = '#0D5CE5';
                e.target.style.boxShadow = '0 0 0 3px rgba(13, 92, 229, 0.1)';
              }}
              onBlur={(e) => {
                e.target.style.backgroundColor = '#F1F4F9';
                e.target.style.borderColor = 'transparent';
                e.target.style.boxShadow = 'none';
              }}
            />
          </div>

          {/* Password input */}
          <div style={{ marginBottom: '22px' }}>
            <label
              htmlFor="login-password"
              style={{
                display: 'block',
                fontSize: '12.5px',
                fontWeight: 500,
                color: '#475569',
                marginBottom: '6px',
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
                height: '42px',
                padding: '0 14px',
                borderRadius: '6px',
                backgroundColor: '#F1F4F9',
                border: '1px solid transparent',
                fontSize: '13.5px',
                color: '#0F172A',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'all 0.15s ease',
              }}
              onFocus={(e) => {
                e.target.style.backgroundColor = '#FFFFFF';
                e.target.style.borderColor = '#0D5CE5';
                e.target.style.boxShadow = '0 0 0 3px rgba(13, 92, 229, 0.1)';
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
              height: '42px',
              borderRadius: '6px',
              backgroundColor: '#0D5CE5',
              color: '#FFFFFF',
              border: 'none',
              fontSize: '14px',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 2px 6px rgba(13, 92, 229, 0.25)',
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
            marginTop: '20px',
            border: '1px solid #E2E8F0',
            borderRadius: '6px',
            padding: '8px 10px 10px 10px',
            backgroundColor: '#FFFFFF',
            boxSizing: 'border-box',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
            }}
          >
            <span style={{ fontSize: '11px', fontWeight: 700, color: '#0F172A' }}>
              Demo Access Roles:
            </span>
            <span style={{ fontSize: '11px', color: '#64748B', fontWeight: 400 }}>
              password: 1
            </span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gap: '3px',
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
                    height: '32px',
                    padding: '0 2px',
                    border: isSelected ? '1px solid #18217E' : '1px solid #CBD5E1',
                    borderRadius: '4px',
                    backgroundColor: isSelected ? '#18217E' : '#FFFFFF',
                    color: isSelected ? '#FFFFFF' : (role.isCustServ ? '#991B1B' : '#1E293B'),
                    fontSize: '10.5px',
                    fontWeight: isSelected ? 700 : 500,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    textAlign: 'center',
                    lineHeight: '1.1',
                    transition: 'all 0.15s ease',
                  }}
                  title={`Login as ${role.label} (${role.email})`}
                >
                  {role.isCustServ ? (
                    <span>
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
