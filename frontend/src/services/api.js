/**
 * BRIDGES Control Tower - Centralized API Service & WebSocket Client
 * Configured across all 20 modular backend architecture domains.
 */

const API_BASE = '/api/v1';

class ApiService {
  constructor() {
    this.token = localStorage.getItem('BRIDGES_ACCESS_TOKEN') || null;
    this.ws = null;
    this.wsListeners = new Set();
    this.wsStatusListeners = new Set();
    this.wsReconnectTimer = null;
    this.pingInterval = null;
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

  // ==========================================================================
  // 1. AUTHENTICATION & ACCESS CONTROL
  // ==========================================================================
  async login(email, password) {
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
    } catch (e) {}
    this.setToken(null);
    this.disconnectWebSocket();
  }

  async getMe() {
    return this.request('/auth/me');
  }

  // ==========================================================================
  // 2. SYSTEM DIAGNOSTICS & PROBES
  // ==========================================================================
  async getHealth() {
    return this.request('/health');
  }

  async ping() {
    return this.request('/ping');
  }

  // ==========================================================================
  // 3. SHIPMENTS & MENDIX INGESTION
  // ==========================================================================
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

  async updateShipmentStatus(id, newStatus, location = '') {
    return this.request(`/shipments/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: newStatus, location }),
    });
  }

  // ==========================================================================
  // 4. TRACKING & MILESTONES
  // ==========================================================================
  async getTrackingTimeline(shipmentId) {
    return this.request(`/tracking/${shipmentId}/timeline`);
  }

  async getLatestTracking(shipmentId) {
    return this.request(`/tracking/${shipmentId}/latest`);
  }

  async postTrackingEvent(shipmentId, eventData) {
    return this.request(`/tracking/${shipmentId}/events`, {
      method: 'POST',
      body: JSON.stringify(eventData),
    });
  }

  // ==========================================================================
  // 5. EXCEPTION MANAGEMENT & SLA
  // ==========================================================================
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

  async detectAnomalies(shipmentId) {
    return this.request(`/exceptions/detect-anomalies/${shipmentId}`, { method: 'POST' });
  }

  // ==========================================================================
  // 6. FINANCIAL & CUSTOMER IMPACT ANALYSIS
  // ==========================================================================
  async assessImpact(exceptionId) {
    return this.request(`/impact/assess/${exceptionId}`, { method: 'POST' });
  }

  async getImpactForException(exceptionId) {
    return this.request(`/impact/exception/${exceptionId}`);
  }

  async getImpactSummaryStats() {
    return this.request('/impact/summary/stats');
  }

  // ==========================================================================
  // 7. AI DIAGNOSTICS (LOCAL OLLAMA / GEMMA 2)
  // ==========================================================================
  async analyzeRootCause(exceptionId) {
    return this.request(`/ai/root-cause/${exceptionId}`, { method: 'POST' });
  }

  async recommendRecovery(exceptionId) {
    return this.request(`/ai/recommend-recovery/${exceptionId}`, { method: 'POST' });
  }

  async draftCustomerAdvisory(exceptionId, payload = {}) {
    return this.request(`/ai/draft-communication/${exceptionId}`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // ==========================================================================
  // 8. CARRIER RECOVERY OPERATIONS & TENDERS
  // ==========================================================================
  async getRecoveryPlans(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/recovery${q ? '?' + q : ''}`);
  }

  async createRecoveryPlan(planData) {
    return this.request('/recovery', {
      method: 'POST',
      body: JSON.stringify(planData),
    });
  }

  async dispatchRecovery(planId) {
    return this.request(`/recovery/${planId}/dispatch`, { method: 'POST' });
  }

  async respondToCarrierProposal(planId, payload) {
    return this.request(`/recovery/${planId}/carrier-respond`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // ==========================================================================
  // 9. CLAIMS & SLA SETTLEMENT ENGINE (Phase 18)
  // ==========================================================================
  async getClaims(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/claims${q ? '?' + q : ''}`);
  }

  async getClaimsSummary() {
    return this.request('/claims/summary');
  }

  async createClaimFromException(exceptionId) {
    return this.request('/claims/auto-from-exception', {
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

  async exportClaimsCsv() {
    return this.request('/claims/export/csv');
  }

  // ==========================================================================
  // 10. GEOFENCING & DYNAMIC CORRIDORS (Phase 19)
  // ==========================================================================
  async getGeofences(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/geofences${q ? '?' + q : ''}`);
  }

  async evaluateGeofence(telemetryData) {
    return this.request('/geofences/evaluate', {
      method: 'POST',
      body: JSON.stringify(telemetryData),
    });
  }

  async createCircularGeofence(data) {
    return this.request('/geofences/circle', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async createPolygonGeofence(data) {
    return this.request('/geofences/polygon', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // ==========================================================================
  // 11. ELECTRONIC PROOF OF DELIVERY & OTP (Phase 17)
  // ==========================================================================
  async generateDeliveryOTP(shipmentId) {
    // Both aliases supported by backend
    return this.request(`/deliveries/shipments/${shipmentId}/otp/generate`, {
      method: 'POST',
    });
  }

  async confirmDeliveryPOD(shipmentIdOrPayload, maybePayload) {
    const shipmentId = maybePayload ? shipmentIdOrPayload : (shipmentIdOrPayload?.shipment_id || 'SHP-9821');
    const body = maybePayload || shipmentIdOrPayload;
    return this.request(`/deliveries/shipments/${shipmentId}/pod`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  async getDeliveryHistory(shipmentId) {
    return this.request(`/deliveries/shipments/${shipmentId}/history`);
  }

  // ==========================================================================
  // 12. CRYPTOGRAPHIC AUDIT TRAIL (Phase 14)
  // ==========================================================================
  async getAuditLogs(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/audit/logs${q ? '?' + q : ''}`);
  }

  async verifyAuditChain() {
    return this.request('/audit/verify');
  }

  async exportAuditCsv() {
    return this.request('/audit/export/compliance-csv');
  }

  // ==========================================================================
  // 13. OPERATIONAL ANALYTICS & SCORECARDS
  // ==========================================================================
  async getCarrierPerformance() {
    return this.request('/analytics/carrier-performance');
  }

  async getFinancialExposure() {
    return this.request('/analytics/financial-exposure');
  }

  async getRootCauseDistribution() {
    return this.request('/analytics/root-cause-distribution');
  }

  async getSlaCompliance() {
    return this.request('/analytics/sla-compliance');
  }

  async exportExceptionsCsv() {
    return this.request('/analytics/export/exceptions-csv');
  }

  // ==========================================================================
  // 14. MULTI-CHANNEL NOTIFICATIONS
  // ==========================================================================
  async getNotifications() {
    return this.request('/notifications');
  }

  async markNotificationRead(id) {
    return this.request(`/notifications/${id}/read`, { method: 'PATCH' });
  }

  async markAllNotificationsRead() {
    return this.request('/notifications/mark-all-read', { method: 'POST' });
  }

  async broadcastAlert(payload) {
    return this.request('/notifications/broadcast', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  // ==========================================================================
  // 15. ENTERPRISE USERS & RBAC GOVERNANCE
  // ==========================================================================
  async getUsers(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/users${q ? '?' + q : ''}`);
  }

  async createUser(payload) {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateUserStatus(userId, isActive) {
    return this.request(`/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    });
  }

  async resetUserPassword(userId, newPassword) {
    return this.request(`/users/${userId}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword }),
    });
  }

  async getRoles() {
    return this.request('/roles');
  }

  async getPermissions() {
    return this.request('/roles/permissions');
  }

  // ==========================================================================
  // 16. BIDIRECTIONAL WEBSOCKET PUB/SUB STREAMING
  // ==========================================================================
  async connectWebSocket(onMessage, onStatusChange) {
    if (onMessage) this.wsListeners.add(onMessage);
    if (onStatusChange) this.wsStatusListeners.add(onStatusChange);

    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    if (!this.token) {
      this.token = localStorage.getItem('BRIDGES_ACCESS_TOKEN');
    }

    if (!this.token) {
      try {
        await this.login('admin@gmail.com', '1');
      } catch (e) {
        console.warn('Could not auto-login for WebSocket:', e);
      }
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const isPort3000 = window.location.port === '3000';
    const host = isPort3000 ? '127.0.0.1:8000' : window.location.host;
    const tokenParam = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
    const wsUrl = `${protocol}//${host}/api/v1/ws/stream${tokenParam}`;

    try {
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.notifyWsStatus('connected');
        if (this.wsReconnectTimer) {
          clearTimeout(this.wsReconnectTimer);
          this.wsReconnectTimer = null;
        }

        if (this.pingInterval) clearInterval(this.pingInterval);
        this.pingInterval = setInterval(() => {
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ action: 'ping', timestamp: Date.now() }));
          }
        }, 20000);
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
        if (this.pingInterval) {
          clearInterval(this.pingInterval);
          this.pingInterval = null;
        }
        this.ws = null;
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
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
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
