import React, { useState } from 'react';
import StatusBadge from '../components/common/StatusBadge';
import {
  Package,
  Search,
  Bot,
  Send,
  CheckCircle2,
  Clock,
  ShieldCheck,
  Thermometer,
} from 'lucide-react';

export default function CustomerPortalView() {
  const [trackingInput, setTrackingInput] = useState('BRG-2843');
  const [chatMessages, setChatMessages] = useState([
    {
      sender: 'ai',
      text: 'Hello Sarah! I am your 24/7 BioPharma Logistics Copilot. How may I assist you with your consignment today?',
    },
  ]);
  const [chatInput, setChatInput] = useState('');

  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userMsg = { sender: 'user', text: chatInput };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatInput('');

    setTimeout(() => {
      let reply = 'Your cryogenic consignment BRG-2843 is securely monitored. Our central team executed an automated cross-dock optimization at Dallas Hub to guarantee sub-zero integrity.';
      if (chatInput.toLowerCase().includes('eta') || chatInput.toLowerCase().includes('when')) {
        reply = 'Consignment BRG-2843 has an approved arrival window of Nov 21 between 14:00 and 15:30 UTC at Denver Mountain Terminal.';
      } else if (chatInput.toLowerCase().includes('temp')) {
        reply = 'Current core temperature is calibrated at continuous pharmaceutical standards. Automated safety pre-checks confirmed ready at Dallas Hub.';
      }
      setChatMessages((prev) => [...prev, { sender: 'ai', text: reply }]);
    }, 600);
  };

  return (
    <div style={{ padding: '24px 28px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Banner */}
      <div style={{ background: '#FFFFFF', padding: '16px 20px', borderRadius: 12, border: '1px solid #E2E8F0' }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0F172A' }}>
          Enterprise Shipper Portal &bull; BioPharma Health Alliance
        </h2>
        <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
          Track confirmed arrival windows, verify cold-chain compliance integrity, and converse with your 24/7 logistics copilot.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: 20 }}>
        {/* Active Consignment Detail */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Tracked Consignment: BRG-2843</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#166534', background: '#EAF7EE', padding: '2px 8px', borderRadius: 9999 }}>
              Cold-Chain Monitored
            </span>
          </div>

          <div style={{ background: '#F8FAFC', padding: 14, borderRadius: 8, marginBottom: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, fontSize: 11.5 }}>
              <div>
                <span style={{ color: '#64748B' }}>Origin Hub</span>
                <div style={{ fontWeight: 700, color: '#0F172A' }}>Dallas Central Hub</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Destination</span>
                <div style={{ fontWeight: 700, color: '#0F172A' }}>Denver Mountain Terminal</div>
              </div>
              <div>
                <span style={{ color: '#64748B' }}>Approved ETA</span>
                <div style={{ fontWeight: 800, color: '#18217E' }}>Nov 21, 14:30 UTC</div>
              </div>
            </div>
          </div>

          {/* Sanitized Milestones */}
          <h4 style={{ margin: '0 0 12px 0', fontSize: 13, fontWeight: 700, color: '#0F172A' }}>
            Verified Transit Progression
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14, borderLeft: '2px solid #CBD5E1', paddingLeft: 16, marginLeft: 8 }}>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: -22, top: 2, width: 10, height: 10, borderRadius: '50%', background: '#10B981' }} />
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0F172A' }}>Consignment Released &amp; Loaded</div>
              <div style={{ fontSize: 11, color: '#64748B' }}>Nov 20, 08:30 UTC • Pre-cooling verified</div>
            </div>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: -22, top: 2, width: 10, height: 10, borderRadius: '50%', background: '#10B981' }} />
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0F172A' }}>Corridor Transit Checkpoint</div>
              <div style={{ fontSize: 11, color: '#64748B' }}>Nov 20, 14:30 UTC • Dallas Corridor Transfer Active</div>
            </div>
            <div style={{ position: 'relative' }}>
              <div style={{ position: 'absolute', left: -22, top: 2, width: 10, height: 10, borderRadius: '50%', background: '#94A3B8' }} />
              <div style={{ fontSize: 12, fontWeight: 700, color: '#64748B' }}>Scheduled Receiving Gate Arrival</div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Denver Mountain Terminal • Nov 21, 14:30 UTC</div>
            </div>
          </div>
        </div>

        {/* 24/7 AI Logistics Copilot */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '480px' }}>
          <div className="panel-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Bot size={16} color="#18217E" />
              <span className="panel-title">24/7 Shipper AI Copilot</span>
            </div>
            <span style={{ fontSize: 10.5, color: '#10B981', fontWeight: 700 }}>● Online</span>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, paddingRight: 4 }}>
            {chatMessages.map((msg, idx) => (
              <div
                key={idx}
                style={{
                  alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                  maxWidth: '85%',
                  background: msg.sender === 'user' ? '#18217E' : '#F1F5F9',
                  color: msg.sender === 'user' ? '#FFFFFF' : '#0F172A',
                  padding: '8px 12px',
                  borderRadius: 10,
                  fontSize: 12,
                  lineHeight: 1.45,
                }}
              >
                {msg.text}
              </div>
            ))}
          </div>

          <form onSubmit={handleSendChat} style={{ display: 'flex', gap: 6, marginTop: 12, paddingTop: 10, borderTop: '1px solid #E2E8F0' }}>
            <input
              type="text"
              placeholder="Ask about shipment ETA, temperature, or customs..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              style={{ flex: 1, height: 34, padding: '0 10px', borderRadius: 6, border: '1px solid #CBD5E1', fontSize: 12, outline: 'none' }}
            />
            <button
              type="submit"
              style={{ padding: '0 12px', borderRadius: 6, background: '#18217E', color: '#FFF', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
            >
              <Send size={14} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
