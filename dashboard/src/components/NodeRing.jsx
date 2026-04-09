import React from 'react';

const NodeRing = ({ node, isSelected, onClick, isLoading = false }) => {
  const hasSoc = typeof node?.soc === 'number';
  const soc = hasSoc ? node.soc : 0;
  const fsmState = node?.fsm_state || 'IDLE';
  
  // Dynamic color based on node state and SoC range
  let strokeColor = 'rgba(255, 255, 255, 0.05)';
  let pulseClass = '';

  if (isLoading) {
    strokeColor = 'rgba(255, 255, 255, 0.15)';
    pulseClass = 'animate-pulse';
  } else if (fsmState === 'P2P_TRADING') {
    strokeColor = '#f59e0b'; // Gold
    pulseClass = 'status-pulse shadow-[0_0_12px_rgba(245,158,11,0.5)]';
  } else if (fsmState === 'EMERGENCY') {
    strokeColor = '#ef4444'; // Red
    pulseClass = 'status-pulse shadow-[0_0_12px_rgba(239,68,68,0.5)]';
  } else {
    // Gradient Stages
    if (soc < 20) strokeColor = '#ef4444';      // Danger
    else if (soc < 50) strokeColor = '#f59e0b'; // Low
    else if (soc < 85) strokeColor = '#10b981'; // Good
    else strokeColor = '#06b6d4';              // Excess/Cyan
  }

  // Ring properties
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (soc / 100) * circumference;

  return (
    <div 
      className={`relative group cursor-pointer transition-all duration-500 flex flex-col items-center ${isSelected ? 'scale-110 z-10' : 'hover:scale-105'}`}
      onClick={onClick}
    >
      <div className={`relative rounded-full p-1 transition-all duration-500 ${isSelected ? 'bg-white/5 ring-1 ring-white/20' : ''}`}>
        <svg width="48" height="48" className="rotate-[-90deg]">
          <circle
            cx="24" cy="24" r={radius}
            fill="transparent"
            stroke="rgba(255,255,255,0.03)"
            strokeWidth="3"
          />
          <circle
            cx="24" cy="24" r={radius}
            fill="transparent"
            stroke={strokeColor}
            strokeWidth="3"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={`transition-all duration-1000 ease-in-out ${pulseClass}`}
          />
        </svg>
        <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[9px] font-mono font-bold transition-colors ${isSelected ? 'text-white' : 'text-white/20 group-hover:text-white/40'}`}>
          {isLoading ? '--' : `${soc.toFixed(0)}%`}
        </div>
      </div>
      
      {isSelected && (
        <span className="absolute -bottom-1.5 w-1 h-1 rounded-full bg-white shadow-[0_0_8px_white]"></span>
      )}
    </div>
  );
};

export default NodeRing;
