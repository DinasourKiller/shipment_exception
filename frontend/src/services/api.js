/**
 * BRIDGES Control Tower - API Client & WebSocket Service
 * Connects React UI to FastAPI backend endpoints (/api/v1)
 */

const API_BASE = '/api/v1';

class ApiService {
  constructor() {
    this.token = localStorage.getItem('BRIDGES_ACCESS_TOKEN') || null;
    this.ws = null;
    this.wsListeners = new Set();
    this.wsStatusListeners = new Set();
    this.wsReconnectTimer = null;
  }

  setToken(token) {
    this.token = token;
    if (token) {
      localStorage.setItem('BRIDGES_ACCESS_TOKEN', token);
    } else {
      localStorage.removeItem('BRIDGES_ACCESS_TOKEN');
    }
  }

  getToken() {
    return this.token;
  }

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') || endpoint.startsWith('/health')
      ? endpoint
      : `${API_BASE}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;

    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    };

    if (this.token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (response.status === 401) {
        // Clear token if expired or unauthorized
        this.setToken(null);
      }

      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        data = await response.text();
      }

      return {
        ok: response.ok,
        status: response.status,
        data,
      };
    } catch (err) {
      console.warn(`API request to ${url} failed:`, err);
      return {
        ok: false,
        status: 0,
        error: err.message,
      };
    }
  }

  // --- Authentication ---
  async login(email, password) {
    // Map demo emails to seeded backend accounts if needed
    let backendEmail = email;
    let backendPass = password;

    const emailLower = (email || '').toLowerCase().trim();
    if (emailLower === 'admin@gmail.com') {
      backendEmail = 'admin@controltower.corp';
      backendPass = 'Password123!';
    } else if (emailLower === 'cta@gmail.com' || emailLower === 'analyst@gmail.com') {
      backendEmail = 'analyst@controltower.corp';
      backendPass = 'Password123!';
    } else if (emailLower === 'dispatcher@gmail.com') {
      backendEmail = 'dispatcher@controltower.corp';
      backendPass = 'Password123!';
    } else if (emailLower === 'carrier@gmail.com') {
      backendEmail = 'carrier@controltower.corp';
      backendPass = 'Password123!';
    } else if (emailLower === 'warehouse@gmail.com' || emailLower === 'manager@gmail.com') {
      backendEmail = 'manager@controltower.corp';
      backendPass = 'Password123!';
    } else if (emailLower === 'cs@gmail.com' || emailLower === 'customer@gmail.com') {
      backendEmail = 'analyst@controltower.corp';
      backendPass = 'Password123!';
    }

    const res = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: backendEmail, password: backendPass }),
    });

    if (res.ok && res.data && res.data.success && res.data.data?.access_token) {
      this.setToken(res.data.data.access_token);
    }
    return res;
  }

  async logout() {
    try {
      await this.request('/auth/logout', { method: 'POST' });
    } catch (e) {
      // Ignore
    }
    this.setToken(null);
    this.disconnectWebSocket();
  }

  // --- System Diagnostics & Health ---
  async getHealth() {
    return this.request('/health');
  }

  async ping() {
    return this.request('/ping');
  }

  // --- Shipments ---
  async getShipments(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/shipments${q ? '?' + q : ''}`);
  }

  async getShipment(id) {
    return this.request(`/shipments/${id}`);
  }

  async syncMendixShipment(trackingRef) {
    return this.request(`/shipments/sync/${trackingRef}`, { method: 'POST' });
  }

  // --- Tracking & Telemetry ---
  async getTrackingTimeline(shipmentId) {
    return this.request(`/tracking/${shipmentId}/timeline`);
  }

  async postTrackingEvent(shipmentId, eventData) {
    return this.request(`/tracking/${shipmentId}/events`, {
      method: 'POST',
      body: JSON.stringify(eventData),
    });
  }

  // --- Exceptions ---
  async getExceptions(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/exceptions${q ? '?' + q : ''}`);
  }

  async getException(id) {
    return this.request(`/exceptions/${id}`);
  }

  async escalateException(id, payload = {}) {
    return this.request(`/exceptions/${id}/escalate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async resolveException(id, payload = {}) {
    return this.request(`/exceptions/${id}/resolve`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Financial & SLA Impact Analysis ---
  async assessImpact(exceptionId) {
    return this.request(`/impact/assess/${exceptionId}`, { method: 'POST' });
  }

  // --- AI Diagnostics ---
  async analyzeRootCause(exceptionId) {
    return this.request(`/ai/root-cause-analysis`, {
      method: 'POST',
      body: JSON.stringify({ exception_id: exceptionId }),
    });
  }

  async draftCustomerAdvisory(payload) {
    return this.request(`/ai/draft-customer-advisory`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Carrier Recovery & Tenders ---
  async getRecoveryPlans(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/recovery${q ? '?' + q : ''}`);
  }

  async createRecoveryPlan(planData) {
    return this.request(`/recovery`, {
      method: 'POST',
      body: JSON.stringify(planData),
    });
  }

  async dispatchRecovery(planId) {
    return this.request(`/recovery/${planId}/dispatch`, { method: 'POST' });
  }

  // --- Claims & SLA Settlement Engine (Phase 18) ---
  async getClaims(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/claims${q ? '?' + q : ''}`);
  }

  async createClaimFromException(exceptionId) {
    return this.request(`/claims/auto-from-exception`, {
      method: 'POST',
      body: JSON.stringify({ exception_id: exceptionId }),
    });
  }

  async settleClaim(claimId, payload = {}) {
    return this.request(`/claims/${claimId}/settle`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async disputeClaim(claimId, payload = {}) {
    return this.request(`/claims/${claimId}/dispute`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Geofencing & Dynamic Corridors (Phase 19) ---
  async getGeofences(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/geofences${q ? '?' + q : ''}`);
  }

  async evaluateGeofence(telemetryData) {
    return this.request(`/geofences/evaluate`, {
      method: 'POST',
      body: JSON.stringify(telemetryData),
    });
  }

  // --- Electronic Proof of Delivery & OTP (Phase 17) ---
  async generateDeliveryOTP(shipmentId) {
    return this.request(`/delivery/otp/generate`, {
      method: 'POST',
      body: JSON.stringify({ shipment_id: shipmentId }),
    });
  }

  async confirmDeliveryPOD(payload) {
    return this.request(`/delivery/pod`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // --- Cryptographic Audit Trail (Phase 14) ---
  async getAuditLogs(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/audit${q ? '?' + q : ''}`);
  }

  async verifyAuditChain() {
    return this.request(`/audit/verify`);
  }

  // --- Analytics & Reports ---
  async getAnalyticsOverview() {
    return this.request(`/analytics/overview`);
  }

  async getCarrierScorecards() {
    return this.request(`/analytics/carriers`);
  }

  // --- Notifications ---
  async getNotifications() {
    return this.request(`/notifications`);
  }

  // --- Users & Roles ---
  async getUsers() {
    return this.request('/users');
  }

  async getRoles() {
    return this.request('/roles');
  }

  // ==========================================================================
  // REAL-TIME WEBSOCKET STREAMING ENGINE
  // ==========================================================================
  connectWebSocket(onMessage, onStatusChange) {
    if (onMessage) this.wsListeners.add(onMessage);
    if (onStatusChange) this.wsStatusListeners.add(onStatusChange);

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // Proxy handles /api/v1/realtime/ws to backend
    const tokenParam = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
    const wsUrl = `${protocol}//${host}/api/v1/realtime/ws${tokenParam}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.notifyWsStatus('connected');
        if (this.wsReconnectTimer) {
          clearTimeout(this.wsReconnectTimer);
          this.wsReconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          this.wsListeners.forEach((fn) => fn(parsed));
        } catch (e) {
          this.wsListeners.forEach((fn) => fn(event.data));
        }
      };

      this.ws.onerror = () => {
        this.notifyWsStatus('error');
      };

      this.ws.onclose = () => {
        this.notifyWsStatus('disconnected');
        this.ws = null;
        // Auto-reconnect after 4s
        if (!this.wsReconnectTimer) {
          this.wsReconnectTimer = setTimeout(() => {
            this.wsReconnectTimer = null;
            this.connectWebSocket();
          }, 4000);
        }
      };
    } catch (err) {
      console.warn('WebSocket connection error:', err);
      this.notifyWsStatus('error');
    }
  }

  disconnectWebSocket() {
    if (this.wsReconnectTimer) {
      clearTimeout(this.wsReconnectTimer);
      this.wsReconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.notifyWsStatus('disconnected');
  }

  notifyWsStatus(status) {
    this.wsStatusListeners.forEach((fn) => fn(status));
  }
}

export const api = new ApiService();
export default api;
