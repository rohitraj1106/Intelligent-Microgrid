import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import mqtt from 'mqtt';

const MicrogridContext = createContext();

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
    if (mqttClient.current && isConnected) {
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
    if (mqttClient.current && isConnected) {
      mqttClient.current.publish('dashboard/active_city', JSON.stringify({ city }));
      console.log(`Signal city change: ${city}`);
    }
  };

  useEffect(() => {
    const client = mqtt.connect('ws://localhost:9001', {
      clientId: `dashboard_${Math.random().toString(16).slice(2, 10)}`,
      clean: true,
      reconnectPeriod: 5000,
    });

    client.on('connect', () => {
      console.log('Connected to MQTT Broker via WebSockets');
      setIsConnected(true);
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

    client.on('close', () => setIsConnected(false));
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
      isConnected 
    }}>
      {children}
    </MicrogridContext.Provider>
  );
};
