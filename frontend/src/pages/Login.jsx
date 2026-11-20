import React, { useState } from 'react';
import { useAuth, DEMO_USERS } from '../context/AuthContext';
import { Layers, ShieldCheck, ArrowRight, Lock, Mail } from 'lucide-react';

export default function Login({ onLoginSuccess }) {
  const { login } = useAuth();
  const [email, setEmail] = useState('admin@gmail.com');
  const [password, setPassword] = useState('1');
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
        setError(result.error || 'Authentication failed. Please verify credentials.');
      }
    } catch (err) {
      setError(err.message || 'An error occurred during authentication.');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickSelect = (demoKey) => {
    const demo = DEMO_USERS[demoKey];
    if (demo) {
      setEmail(demo.email);
      setPassword('1');
    }
  };

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', background: '#F8FAFC' }}>
      {/* Left Column: Form & Demo Credentials */}
      <div
        style={{
          width: '480px',
          minWidth: '380px',
          background: '#FFFFFF',
          padding: '40px 48px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          borderRight: '1px solid #E2E8F0',
          boxShadow: '4px 0 24px rgba(0,0,0,0.03)',
          overflowY: 'auto',
        }}
      >
        <div>
          {/* Brand Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 36 }}>
            <div
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                background: '#18217E',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 4px 10px rgba(24, 33, 126, 0.3)',
              }}
            >
              <Layers size={22} color="#FFFFFF" />
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color: '#070724', letterSpacing: '0.5px' }}>
                BRIDGES
              </div>
              <div style={{ fontSize: 11, fontWeight: 600, color: '#64748B' }}>
                Exception Control Tower Platform
              </div>
            </div>
          </div>

          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 22, fontWeight: 800, color: '#0F172A', margin: '0 0 6px 0' }}>
              Sign in to Workspace
            </h2>
            <p style={{ fontSize: 13, color: '#64748B', margin: 0 }}>
              Access multimodal telemetry, live exception triage & recovery tenders.
            </p>
          </div>

          {error && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 8,
                background: '#FDE8E6',
                border: '1px solid #FCA5A5',
                color: '#EA341F',
                fontSize: 12,
                fontWeight: 600,
                marginBottom: 20,
              }}
            >
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                Work Email Address
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: 12, color: '#94A3B8' }}>
                  <Mail size={16} />
                </span>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@gmail.com"
                  style={{
                    width: '100%',
                    height: 42,
                    padding: '0 12px 0 38px',
                    borderRadius: 8,
                    border: '1.5px solid #CBD5E1',
                    fontSize: 13,
                    fontWeight: 500,
                    outline: 'none',
                    color: '#0F172A',
                  }}
                />
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 6 }}>
                Security Password
              </label>
              <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                <span style={{ position: 'absolute', left: 12, color: '#94A3B8' }}>
                  <Lock size={16} />
                </span>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password '1'"
                  style={{
                    width: '100%',
                    height: 42,
                    padding: '0 12px 0 38px',
                    borderRadius: 8,
                    border: '1.5px solid #CBD5E1',
                    fontSize: 13,
                    fontWeight: 500,
                    outline: 'none',
                    color: '#0F172A',
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              style={{
                height: 44,
                borderRadius: 8,
                background: '#18217E',
                color: '#FFFFFF',
                border: 'none',
                fontSize: 14,
                fontWeight: 700,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                boxShadow: '0 4px 12px rgba(24, 33, 126, 0.25)',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{loading ? 'Authenticating...' : 'Sign In to Control Tower'}</span>
              <ArrowRight size={16} />
            </button>
          </form>

          {/* Quick Demo Role Selector Chips */}
          <div style={{ marginTop: 28, paddingTop: 20, borderTop: '1px solid #F1F5F9' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: 10 }}>
              Quick Demo Workspaces (Click to autofill)
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <button
                type="button"
                onClick={() => handleQuickSelect('admin')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.admin.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.admin.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🛡️ Admin
              </button>
              <button
                type="button"
                onClick={() => handleQuickSelect('analyst')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.analyst.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.analyst.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🔬 Analyst
              </button>
              <button
                type="button"
                onClick={() => handleQuickSelect('dispatcher')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.dispatcher.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.dispatcher.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🚚 Dispatcher
              </button>
              <button
                type="button"
                onClick={() => handleQuickSelect('carrier')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.carrier.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.carrier.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🚛 Carrier
              </button>
              <button
                type="button"
                onClick={() => handleQuickSelect('warehouse')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.warehouse.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.warehouse.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🏭 Warehouse
              </button>
              <button
                type="button"
                onClick={() => handleQuickSelect('cs')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.cs.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.cs.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🎧 CS Care
              </button>
              <button
                type="button"
                onClick={() => handleQuickSelect('customer')}
                style={{
                  padding: '5px 10px',
                  borderRadius: 6,
                  border: '1px solid #CBD5E1',
                  background: email === DEMO_USERS.customer.email ? '#EEF2FF' : '#F8FAFC',
                  color: email === DEMO_USERS.customer.email ? '#18217E' : '#334155',
                  fontSize: 11.5,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                🏢 Shipper
              </button>
            </div>
            <p style={{ fontSize: 11, color: '#94A3B8', marginTop: 8 }}>
              All demo accounts share password: <code style={{ fontWeight: 700, color: '#18217E' }}>1</code> (or <code style={{ fontWeight: 700 }}>Password123!</code>).
            </p>
          </div>
        </div>

        {/* Footer info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#94A3B8' }}>
          <ShieldCheck size={14} color="#10B981" />
          <span>Secured by RS256 JWT &amp; SHA-256 Audit Trail • v1.0.0</span>
        </div>
      </div>

      {/* Right Column: Hero Graphic */}
      <div
        style={{
          flex: 1,
          background: 'linear-gradient(135deg, #09104D 0%, #18217E 60%, #424989 100%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 60,
          color: '#FFFFFF',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ maxWidth: 560, zIndex: 10, textAlign: 'center' }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 16px',
              borderRadius: 9999,
              background: 'rgba(255, 255, 255, 0.12)',
              backdropFilter: 'blur(8px)',
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: '0.5px',
              marginBottom: 24,
              border: '1px solid rgba(255, 255, 255, 0.2)',
            }}
          >
            ✦ ENTERPRISE MULTIMODAL CONTROL TOWER
          </div>
          <h1 style={{ fontSize: 36, fontWeight: 800, lineHeight: 1.25, margin: '0 0 16px 0', letterSpacing: '-0.02em' }}>
            Transform Logistics Exceptions into Actionable Recovery.
          </h1>
          <p style={{ fontSize: 15, lineHeight: 1.6, opacity: 0.85, margin: '0 0 32px 0' }}>
            Unified real-time IoT &amp; GPS telematics, automated dynamic corridor departure alerts, carrier recovery tender dispatching, and cryptographic SLA claims settlement.
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 16,
              background: 'rgba(255, 255, 255, 0.08)',
              padding: 20,
              borderRadius: 14,
              border: '1px solid rgba(255, 255, 255, 0.15)',
              backdropFilter: 'blur(10px)',
            }}
          >
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#60A5FA' }}>94.8%</div>
              <div style={{ fontSize: 11, opacity: 0.8, marginTop: 2 }}>On-Time Delivery Rate</div>
            </div>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#34D399' }}>&lt; 15 min</div>
              <div style={{ fontSize: 11, opacity: 0.8, marginTop: 2 }}>Average Exception Triage</div>
            </div>
            <div>
              <div style={{ fontSize: 24, fontWeight: 800, color: '#F87171' }}>100%</div>
              <div style={{ fontSize: 11, opacity: 0.8, marginTop: 2 }}>Hash-Chained Audit Trail</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
