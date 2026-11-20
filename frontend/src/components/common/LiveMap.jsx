import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

// Hub coordinates
const HUBS = [
  { id: 'DAL', name: 'Dallas SuperCenter', lat: 32.7767, lng: -96.797, type: 'Regional Hub', activeCount: 42 },
  { id: 'LIT', name: 'Little Rock Cross-Dock', lat: 34.7465, lng: -92.2896, type: 'Cross-Dock', activeCount: 18 },
  { id: 'MEM', name: 'Memphis Intermodal Nexus', lat: 35.1495, lng: -90.049, type: 'Intermodal Nexus', activeCount: 56 },
  { id: 'CHI', name: 'Chicago Freight Terminal', lat: 41.8781, lng: -87.6298, type: 'Intermodal Rail', activeCount: 64 },
  { id: 'ATL', name: 'Atlanta Southeast Gateway', lat: 33.749, lng: -84.388, type: 'Southeast Gateway', activeCount: 38 },
  { id: 'NYC', name: 'New York Metro Port', lat: 40.7128, lng: -74.006, type: 'Metropolitan Cargo Port', activeCount: 47 },
  { id: 'LAX', name: 'Los Angeles Ocean Port', lat: 33.7432, lng: -118.2673, type: 'Deepwater Pacific Port', activeCount: 51 },
  { id: 'HOU', name: 'Houston Gulf Port', lat: 29.7604, lng: -95.3698, type: 'Gulf Intermodal Sea Port', activeCount: 33 },
  { id: 'DEN', name: 'Denver Mountain Terminal', lat: 39.7392, lng: -104.9903, type: 'Mountain Intermodal', activeCount: 22 },
];

// Sample active carrier vehicles
const VEHICLES = [
  { id: 'TRK-2843', label: 'BRG-2843 (BioPharma Cryo)', lat: 33.95, lng: -94.5, status: 'Critical', speed: '58 mph', temp: '-14.2°C', driver: 'Marcus Vance' },
  { id: 'TRK-1092', label: 'BRG-1092 (Electronics)', lat: 36.2, lng: -88.7, status: 'In Transit', speed: '63 mph', temp: '21.0°C', driver: 'Norman Reedus' },
  { id: 'TRK-4401', label: 'BRG-4401 (Auto Components)', lat: 31.5, lng: -96.0, status: 'On Schedule', speed: '61 mph', temp: '20.5°C', driver: 'Dave Miller' },
  { id: 'TRK-7719', label: 'BRG-7719 (Pharma Supply)', lat: 38.6, lng: -90.2, status: 'Delayed', speed: '24 mph', temp: '4.1°C', driver: 'Elena Hayes' },
  { id: 'TRK-9023', label: 'BRG-9023 (Heavy Freight)', lat: 34.2, lng: -85.5, status: 'In Transit', speed: '60 mph', temp: '19.8°C', driver: 'Jack R.' },
];

export default function LiveMap({ height = '420px', interactive = true, selectedShipment = null }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Clean up if already initialized
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    // Initialize Leaflet Map centered on US midwest/south corridors
    const map = L.map(mapContainerRef.current, {
      center: [36.5, -93.5],
      zoom: 5,
      zoomControl: interactive,
      dragging: interactive,
      scrollWheelZoom: false,
    });

    mapInstanceRef.current = map;

    // Esri World Street Map layer
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
      attribution: '&copy; Esri &mdash; BRIDGES Telemetry Engine',
      maxZoom: 18,
    }).addTo(map);

    // Render Hubs
    HUBS.forEach((hub) => {
      const hubIcon = L.divIcon({
        className: 'custom-hub-marker',
        html: `
          <div style="background: #18217E; color: #fff; width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 800; border: 2px solid #fff; box-shadow: 0 2px 6px rgba(0,0,0,0.35);">
            ${hub.id}
          </div>
        `,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });

      const marker = L.marker([hub.lat, hub.lng], { icon: hubIcon }).addTo(map);
      marker.bindPopup(`
        <div style="padding: 4px; font-family: 'Plus Jakarta Sans', sans-serif;">
          <strong style="color: #18217E; font-size: 13px;">${hub.name}</strong><br/>
          <span style="font-size: 11px; color: #64748B;">Type: ${hub.type}</span><br/>
          <span style="font-size: 11px; font-weight: 600; color: #0F172A;">Active Units: ${hub.activeCount}</span>
        </div>
      `);
    });

    // Render Corridors / Polylines between major hubs
    const corridors = [
      [[32.7767, -96.797], [34.7465, -92.2896], [35.1495, -90.049]], // I-30 Dallas to Memphis
      [[35.1495, -90.049], [38.627, -90.1994], [41.8781, -87.6298]], // I-55 Memphis to Chicago
      [[32.7767, -96.797], [29.7604, -95.3698]], // I-45 Dallas to Houston
      [[35.1495, -90.049], [33.749, -84.388]], // I-22 / I-20 to Atlanta
    ];

    corridors.forEach((poly) => {
      L.polyline(poly, {
        color: '#424989',
        weight: 2.5,
        opacity: 0.65,
        dashArray: '5, 8',
      }).addTo(map);
    });

    // Render In-Transit Carrier Vehicles
    VEHICLES.forEach((v) => {
      const isCritical = v.status === 'Critical';
      const isDelayed = v.status === 'Delayed';
      const bgColor = isCritical ? '#EA341F' : isDelayed ? '#B45309' : '#10B981';

      const truckIcon = L.divIcon({
        className: 'custom-truck-marker',
        html: `
          <div style="background: ${bgColor}; color: #fff; width: 22px; height: 22px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 700; border: 2px solid #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.3); ${isCritical ? 'animation: pulse 1.5s infinite;' : ''}">
            ⛟
          </div>
        `,
        iconSize: [22, 22],
        iconAnchor: [11, 11],
      });

      const marker = L.marker([v.lat, v.lng], { icon: truckIcon }).addTo(map);
      marker.bindPopup(`
        <div style="padding: 6px; font-family: 'Plus Jakarta Sans', sans-serif; min-width: 170px;">
          <div style="font-weight: 700; font-size: 13px; color: #0F172A; margin-bottom: 4px;">${v.label}</div>
          <div style="font-size: 11px; margin-bottom: 2px;">Status: <span style="font-weight: 600; color: ${bgColor}">${v.status}</span></div>
          <div style="font-size: 11px; color: #475569;">Speed: <strong>${v.speed}</strong></div>
          <div style="font-size: 11px; color: #475569;">Cargo Temp: <strong style="color: ${v.temp.startsWith('-') ? '#1D4ED8' : '#334155'}">${v.temp}</strong></div>
          <div style="font-size: 11px; color: #475569;">Operator: ${v.driver}</div>
        </div>
      `);
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [interactive]);

  return (
    <div style={{ position: 'relative', width: '100%', height, borderRadius: '12px', overflow: 'hidden', border: '1px solid #E2E8F0' }}>
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />
      <div
        style={{
          position: 'absolute',
          bottom: 10,
          left: 12,
          zIndex: 400,
          background: 'rgba(255, 255, 255, 0.94)',
          backdropFilter: 'blur(4px)',
          padding: '6px 12px',
          borderRadius: '8px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          fontSize: '11px',
          fontWeight: 600,
        }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#18217E' }} /> Central Hubs
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981' }} /> Normal
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#B45309' }} /> Delayed
        </span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#EA341F' }} /> Critical / SLA
        </span>
      </div>
    </div>
  );
}
