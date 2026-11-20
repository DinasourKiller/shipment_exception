import React, { useState } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import {
  Flame,
  Users,
  Send,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function WarRoomView({ onNavigate }) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'Sarah Lin (Control Tower Analyst)',
      time: '14:32 UTC',
      text: 'Incident declared for BRG-2843. Core temperature breached -20.0°C. Secondary compressor stalled. Initiating emergency divert protocol.',
      role: 'analyst',
    },
    {
      id: 2,
      sender: 'Elena Rostova (Dispatcher)',
      time: '14:35 UTC',
      text: 'Route evaluated. Diverting truck to Dallas Central Hub (WH-DAL-01) adds only 45 minutes transit delay vs total loss in Denver.',
      role: 'dispatcher',
    },
    {
      id: 3,
      sender: 'Carlos Mendoza (Warehouse Supervisor)',
      time: '14:38 UTC',
      text: 'Dock Door #4 pre-allocated at Dallas Hub. Relief trailer BG-12 is pre-cooled to -25.0°C and standing by.',
      role: 'warehouse',
    },
    {
      id: 4,
      sender: 'Marcus Vance (Carrier Operations)',
      time: '14:41 UTC',
      text: 'Carrier team is alerted. Standing by in tender queue to accept REC-2005 immediately upon issuance.',
      role: 'carrier',
    },
  ]);

  const [inputMsg, setInputMsg] = useState('');
  const [votes, setVotes] = useState({ yes: 4, total: 5, userVoted: false });

  const handleSendMessage = (e) => {
    e.preventDefault();
    if (!inputMsg.trim()) return;
    const newMsg = {
      id: Date.now(),
      sender: `${user?.name || 'Operator'} (${user?.role || 'Analyst'})`,
      time: new Date().toISOString().substring(11, 16) + ' UTC',
      text: inputMsg,
      role: 'user',
    };
    setMessages((prev) => [...prev, newMsg]);
    setInputMsg('');
  };

  const handleVote = () => {
    if (votes.userVoted) return;
    setVotes({ ...votes, yes: votes.yes + 1, userVoted: true });
    showToast('Consensus vote recorded: Reroute Authorized', 'success');
  };

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* War Room Header */}
      <div
        style={{
          background: 'linear-gradient(90deg, #18217E 0%, #09104D 100%)',
          color: '#FFF',
          padding: '18px 24px',
          borderRadius: 14,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 4px 14px rgba(9, 16, 77, 0.25)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ background: '#EA341F', color: '#FFF', padding: '2px 8px', borderRadius: 4, fontSize: 10, fontWeight: 800 }}>
              LIVE WAR ROOM
            </span>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>
              Incident #WR-2026-081: Cryo-Vaccine Thermal Rescue
            </h2>
          </div>
          <p style={{ margin: '4px 0 0', fontSize: 12, opacity: 0.85 }}>
            Consignment BRG-2843 • BioPharma Health Alliance • Stakeholders: Analyst, Dispatcher, Carrier, Warehouse
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, background: 'rgba(255,255,255,0.12)', padding: '6px 12px', borderRadius: 8 }}>
            <Users size={14} />
            <span>4 Active Collaborators</span>
          </div>
          <button
            onClick={() => onNavigate('recovery')}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              background: '#EA341F',
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
            <RefreshCw size={14} />
            <span>Issue Expedited Tender</span>
          </button>
        </div>
      </div>

      {/* Main Grid: Live Collaboration Stream & Consensus Card */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
        {/* Chat / Event Stream */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '520px' }}>
          <div className="panel-header">
            <span className="panel-title">Multi-Stakeholder Incident Stream</span>
            <span style={{ fontSize: 11, color: '#10B981', fontWeight: 700 }}>● Encrypted Channel</span>
          </div>

          {/* Messages scroll box */}
          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12, paddingRight: 6 }}>
            {messages.map((m) => (
              <div
                key={m.id}
                style={{
                  background: m.role === 'analyst' ? '#F8FAFC' : m.role === 'warehouse' ? '#F0FDF4' : m.role === 'dispatcher' ? '#EEF2FF' : '#FFFBEB',
                  border: '1px solid #E2E8F0',
                  borderRadius: 10,
                  padding: '10px 14px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <strong style={{ fontSize: 12, color: '#0F172A' }}>{m.sender}</strong>
                  <span style={{ fontSize: 10.5, color: '#94A3B8' }}>{m.time}</span>
                </div>
                <div style={{ fontSize: 12.5, color: '#334155', lineHeight: 1.45 }}>{m.text}</div>
              </div>
            ))}
          </div>

          {/* Message Input Box */}
          <form onSubmit={handleSendMessage} style={{ display: 'flex', gap: 8, marginTop: 14, paddingTop: 12, borderTop: '1px solid #E2E8F0' }}>
            <input
              type="text"
              placeholder="Type operational update or recovery instruction..."
              value={inputMsg}
              onChange={(e) => setInputMsg(e.target.value)}
              style={{
                flex: 1,
                height: 38,
                padding: '0 12px',
                borderRadius: 8,
                border: '1px solid #CBD5E1',
                fontSize: 12.5,
                outline: 'none',
              }}
            />
            <button
              type="submit"
              style={{
                padding: '0 16px',
                borderRadius: 8,
                background: '#18217E',
                color: '#FFF',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Send size={15} />
            </button>
          </form>
        </div>

        {/* Situation Brief & Consensus Vote Panel */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Consensus Voting Card */}
          <div className="panel" style={{ borderLeft: '4px solid #10B981' }}>
            <div className="panel-header">
              <span className="panel-title">Consensus Recovery Authorization</span>
            </div>
            <p style={{ margin: '0 0 12px 0', fontSize: 12, color: '#475569', lineHeight: 1.45 }}>
              Proposed Directive: Commit emergency reroute to Dallas WH-DAL-01 and issue Expedited Tender REC-2005.
            </p>

            <div style={{ background: '#F8FAFC', padding: 12, borderRadius: 8, marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 700, color: '#0F172A' }}>
                <span>Authorization Quorum</span>
                <span style={{ color: '#166534' }}>{votes.yes}/{votes.total} Approved</span>
              </div>
              <div style={{ height: 6, background: '#E2E8F0', borderRadius: 3, marginTop: 6, overflow: 'hidden' }}>
                <div style={{ width: `${(votes.yes / votes.total) * 100}%`, height: '100%', background: '#10B981' }} />
              </div>
            </div>

            <button
              onClick={handleVote}
              disabled={votes.userVoted}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: 8,
                background: votes.userVoted ? '#E2E8F0' : '#10B981',
                color: votes.userVoted ? '#64748B' : '#FFFFFF',
                border: 'none',
                fontSize: 12.5,
                fontWeight: 700,
                cursor: votes.userVoted ? 'default' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
              }}
            >
              <CheckCircle2 size={15} />
              <span>{votes.userVoted ? 'Your Vote Cast (Approved)' : 'Cast Vote: Approve Action'}</span>
            </button>
          </div>

          {/* Quick SLA Breaches Panel */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">SLA Penalty Protection</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 11.5 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748B' }}>Breach Countdown</span>
                <strong style={{ color: '#EA341F' }}>16 minutes</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748B' }}>Potential Claim</span>
                <strong style={{ color: '#EA341F' }}>$15,000.00</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#64748B' }}>Saved by Reroute</span>
                <strong style={{ color: '#10B981' }}>$85,000 Cargo Value</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
