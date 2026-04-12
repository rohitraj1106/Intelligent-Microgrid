import React from 'react';
import { useMicrogrid } from '../context/MicrogridContext';
import NodeRing from './NodeRing';

const CITIES = [
  { id: 'delhi', name: 'Delhi', color: 'rgba(16, 185, 129, 0.4)', accent: 'emerald' },
  { id: 'noida', name: 'Noida', color: 'rgba(59, 130, 246, 0.4)', accent: 'blue' },
  { id: 'gurugram', name: 'Gurugram', color: 'rgba(245, 158, 11, 0.4)', accent: 'amber' },
  { id: 'chandigarh', name: 'Chandigarh', color: 'rgba(139, 92, 246, 0.4)', accent: 'violet' },
  { id: 'dehradun', name: 'Dehradun', color: 'rgba(236, 72, 153, 0.4)', accent: 'pink' }
];

const CityMap = ({ onCitySelect }) => {
  const { nodes, selectedNodeId, setSelectedNodeId } = useMicrogrid();

  return (
    <div className="flex flex-col gap-8 p-8 overflow-y-auto max-h-[100vh] scrollbar-hide">
      {/* Top Row: Delhi, Noida, Gurugram */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {CITIES.slice(0, 3).map(city => (
          <CityCard 
            key={city.id} 
            city={city} 
            nodes={nodes} 
            selectedNodeId={selectedNodeId} 
            setSelectedNodeId={setSelectedNodeId} 
            onCitySelect={() => onCitySelect(city.id)}
          />
        ))}
      </div>
      
      {/* Bottom Row: Chandigarh, Dehradun */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-[66%] mx-auto lg:mx-0">
        {CITIES.slice(3).map(city => (
          <CityCard 
            key={city.id} 
            city={city} 
            nodes={nodes} 
            selectedNodeId={selectedNodeId} 
            setSelectedNodeId={setSelectedNodeId} 
            onCitySelect={() => onCitySelect(city.id)}
          />
        ))}
      </div>
    </div>
  );
};

const CityCard = ({ city, nodes, selectedNodeId, setSelectedNodeId, onCitySelect }) => {
  const cityNodes = [...Array(15)].map((_, i) => `${city.id}_${i.toString().padStart(2, '0')}`);
  const socValues = cityNodes
    .map(id => nodes[id]?.soc)
    .filter(value => typeof value === 'number');
  const avgSoc = socValues.length ? (socValues.reduce((acc, value) => acc + value, 0) / socValues.length) : null;

  return (
    <div 
      className="glass-card relative overflow-hidden group hover:bg-white/5 transition-all duration-500 cursor-pointer"
      onClick={onCitySelect}
    >
      <div className="absolute top-0 left-0 w-full h-1" style={{ backgroundColor: city.color }}></div>
      <div className="p-6">
        <div className="flex items-end justify-between mb-4">
          <div>
            <h3 className="text-2xl font-black tracking-tighter text-white/95 uppercase italic group-hover:text-white transition-colors">{city.name}</h3>
            <p className="text-[10px] font-bold text-white/30 tracking-[0.2em]">15 EDGE NODES</p>
          </div>
          <div className="text-right">
            <span className="text-lg font-mono text-white/60">{avgSoc === null ? '--' : `${avgSoc.toFixed(0)}%`}</span>
            <p className="text-[9px] font-bold text-white/20">AVG SOC</p>
          </div>
        </div>
        
        <div className="mb-6 flex items-center justify-between text-[8px] font-black uppercase tracking-widest text-emerald-500/40 group-hover:text-emerald-500 transition-colors">
           <span>Click to Activate Intelligence →</span>
        </div>

        <div className="grid grid-cols-5 gap-3 opacity-60 group-hover:opacity-100 transition-opacity">
          {cityNodes.slice(0, 10).map(nodeId => {
            const node = nodes[nodeId];
            const isLoading = typeof node?.soc !== 'number';
            const displayNode = node || { id: nodeId, city: city.id, soc: 0, fsm_state: 'IDLE' };
            return (
              <NodeRing 
                key={nodeId} 
                node={displayNode}
                isLoading={isLoading}
                isSelected={selectedNodeId === nodeId}
                onClick={(e) => {
                    e.stopPropagation(); // Don't trigger city select
                    setSelectedNodeId(nodeId);
                }}
              />
            );
          })}
          <div className="flex items-center justify-center text-[10px] text-white/10 font-bold">
            +5
          </div>
        </div>
      </div>
    </div>
  );
};

export default CityMap;
