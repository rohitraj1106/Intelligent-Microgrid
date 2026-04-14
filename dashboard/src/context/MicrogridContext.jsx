import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import mqtt from 'mqtt';
import { getNodesHealth } from '../api/nodes';
import { subscribeGatewayEvents } from '../api/events';
import { getSystemHealth } from '../api/system';

const MicrogridContext = createContext();
const TRACE_MQTT_ENABLED = (import.meta.env.VITE_TRACE_MQTT_ENABLED ?? 'true') !== 'false';
const MQTT_WS_URL = import.meta.env.VITE_MQTT_WS_URL || 'ws://localhost:9001';

export const useMicrogrid = () => {
  const context = useContext(MicrogridContext);
  if (!context) {
    throw new Error('useMicrogrid must be used within a MicrogridProvider');
  }
  return context;
};

export const MicrogridProvider = ({ children }) => {
  const [nodes, setNodes] = useState({});
  const [selectedNodeId, setSelectedNodeId] = useState('delhi_00');
  const [activeCity, setActiveCity] = useState(null); // 'delhi', 'noida', etc.
  const [isConnected, setIsConnected] = useState(false);
  const [mqttConnected, setMqttConnected] = useState(false);
  const [serviceHealth, setServiceHealth] = useState({
    api: 'down',
    marketplace: 'down',
    mqttBridge: 'down',
  });
  
  // All trace data for all nodes, organized by type
  const [allTraces, setAllTraces] = useState({
    telemetry: {},
    forecast: {},
    agent: {},
    orchestrator: {}
  });

  const mqttClient = useRef(null);
  const selectedNodeRef = useRef(selectedNodeId);

  // Method to signal node selection to backend
  const updateSelectedNode = (nodeId) => {
    setSelectedNodeId(nodeId);
    if (TRACE_MQTT_ENABLED && mqttClient.current && mqttConnected) {
      mqttClient.current.publish('dashboard/selected_node', JSON.stringify({ node_id: nodeId }));
      console.log(`Signal node selection: ${nodeId}`);
    }
  };

  useEffect(() => {
    selectedNodeRef.current = selectedNodeId;
  }, [selectedNodeId]);

  // Method to signal active city change to backend
  const updateActiveCity = (city) => {
    setActiveCity(city);
    if (TRACE_MQTT_ENABLED && mqttClient.current && mqttConnected) {
      mqttClient.current.publish('dashboard/active_city', JSON.stringify({ city }));
      console.log(`Signal city change: ${city}`);
    }
  };

  useEffect(() => {
    let mounted = true;

    const pollHealth = async () => {
      try {
        const health = await getSystemHealth();
        if (!mounted) return;

        setServiceHealth({
          api: health?.api?.status || 'down',
          marketplace: health?.marketplace_upstream?.status || 'down',
          mqttBridge: health?.mqtt_bridge?.status || 'down',
        });
      } catch (error) {
        if (!mounted) return;
        setServiceHealth({ api: 'down', marketplace: 'down', mqttBridge: 'down' });
      }
    };

    pollHealth();
    const interval = setInterval(pollHealth, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    const fetchNodeHealth = async () => {
      try {
        const rows = await getNodesHealth({ city: activeCity || undefined });
        if (!mounted) return;

        const mapped = rows.reduce((acc, row) => {
          acc[row.node_id] = {
            id: row.node_id,
            city: row.city,
            soc: Number(row.soc_pct) || 0,
            solar: Number(row.solar_kw) || 0,
            load: Number(row.load_kw) || 0,
            fsm_state: row.fsm_state || null,
            strategy_status: row.strategy_status || null,
            stale: row.stale,
            updated_at: row.timestamp,
          };
          return acc;
        }, {});

        setNodes(prev => ({ ...prev, ...mapped }));
        setIsConnected(true);
      } catch (error) {
        console.error('Gateway node-health fetch failed:', error);
        setIsConnected(false);
      }
    };

    fetchNodeHealth();
    const interval = setInterval(fetchNodeHealth, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [activeCity]);

  useEffect(() => {
    const eventSource = subscribeGatewayEvents();
    eventSource.addEventListener('node_state', (event) => {
      try {
        const payload = JSON.parse(event.data || '{}');
        const telemetry = payload.telemetry || {};
        const orchestrator = payload.orchestrator || {};
        const nodeId = payload.node_id;
        if (!nodeId) return;

        setNodes(prev => ({
          ...prev,
          [nodeId]: {
            ...(prev[nodeId] || { id: nodeId, city: payload.city || nodeId.split('_')[0] }),
            soc: Number(telemetry.soc_pct) || 0,
            voltage: Number(telemetry.voltage_v) || 0,
            solar: Number(telemetry.power_solar_kw) || 0,
            load: Number(telemetry.power_load_kw) || 0,
            fsm_state: orchestrator.fsm_state || null,
            strategy_status: orchestrator.strategy_status || null,
            stale: Boolean(payload.stale),
            updated_at: payload.timestamp,
          },
        }));
      } catch (error) {
        console.error('Gateway event parse error:', error);
      }
    });

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => eventSource.close();
  }, []);

  useEffect(() => {
    if (!TRACE_MQTT_ENABLED) {
      return undefined;
    }

    const client = mqtt.connect(MQTT_WS_URL, {
      clientId: `dashboard_${Math.random().toString(16).slice(2, 10)}`,
      clean: true,
      reconnectPeriod: 5000,
    });

    client.on('connect', () => {
      console.log('Connected to MQTT Broker via WebSockets');
      setMqttConnected(true);
      client.subscribe(['dashboard/trace/#', 'dashboard/active_city', 'dashboard/selected_node'], (err) => {
        if (err) console.error('Subscription error:', err);
      });
    });

    client.on('message', (topic, message) => {
      try {
        const payload = JSON.parse(message.toString());
        
        if (topic === 'dashboard/active_city') {
          setActiveCity(payload.city);
          return;
        }

        if (topic === 'dashboard/selected_node') {
          setSelectedNodeId(payload.node_id);
          return;
        }

        const parts = topic.split('/');
        const nodeId = parts[2];
        const component = parts[3];

        // Update basic node info (for overview maps/lists)
        if (component === 'edge' || component === 'orchestrator') {
          setNodes(prev => {
            const node = prev[nodeId] || { id: nodeId, city: nodeId.split('_')[0] };
            if (component === 'edge') {
              node.soc = payload.output.soc_pct;
              node.voltage = payload.output.voltage_v;
              node.solar = payload.output.power_solar_kw;
              node.load = payload.output.power_load_kw;
            } else if (component === 'orchestrator') {
              node.fsm_state = payload.output.fsm_state;
              node.strategy_status = payload.output.strategy_status;
            }
            return { ...prev, [nodeId]: { ...node } };
          });
        }

        // Store specialized trace data for every node
        const traceKey = component === 'edge' ? 'telemetry' : component;

        // BRAIN GUARD: If an agent message is simulated but for the selected node, drop it.
        // This prevents background pulses from overwriting focused Gemini reasoning.
        if (traceKey === 'agent' && nodeId === selectedNodeRef.current) {
          if (payload.reasoning && payload.reasoning.includes('[SIMULATED]')) {
            return; // Ignore simulated background pulses for focused node
          }
        }

        setAllTraces(prev => ({
          ...prev,
          [traceKey]: {
            ...prev[traceKey],
            [nodeId]: payload
          }
        }));

      } catch (e) {
        console.error('Error parsing MQTT message:', e);
      }
    });

    client.on('close', () => setMqttConnected(false));
    mqttClient.current = client;

    return () => {
      if (client) client.end();
    };
  }, []);

  return (
    <MicrogridContext.Provider value={{ 
      nodes, 
      selectedNodeId, 
      setSelectedNodeId: updateSelectedNode, 
      activeCity, 
      setActiveCity: updateActiveCity,
      traceData: {
        telemetry: allTraces.telemetry[selectedNodeId] || null,
        forecast: allTraces.forecast[selectedNodeId] || null,
        agent: allTraces.agent[selectedNodeId] || null,
        orchestrator: allTraces.orchestrator[selectedNodeId] || null,
      },
      allTraces,
      isConnected,
      mqttConnected,
      traceMqttEnabled: TRACE_MQTT_ENABLED,
      serviceHealth,
    }}>
      {children}
    </MicrogridContext.Provider>
  );
};
