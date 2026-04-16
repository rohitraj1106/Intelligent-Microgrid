import React from 'react';
import { TrendingUp, Battery, Zap, Sun } from 'lucide-react';

const HouseholdCard = ({ node, isSelected, onClick, agentData }) => {
  const soc = node?.soc || 0;
  const verdict = agentData?.output?.action || 'HOLD';
  const amount = agentData?.output?.amount_kwh || 0;
  const batteryPower = Number(node?.batteryPower || 0);
  const gridImport = Number(node?.gridImport || 0);
  const gridExport = Number(node?.gridExport || 0);
  const batteryCapacity = Number(node?.batteryCapacityKwh || 0);
  const voltage = Number(node?.voltage || 0);
  const tier = node?.tier || 'standard';

  // Verdict Styling
  const getVerdictStyles = () => {
    switch (verdict) {
      case 'BUY': return 'bg-blue-500/10 border-blue-500/30 text-blue-400';
      case 'SELL': return 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400';
      default: return 'bg-white/5 border-white/10 text-white/40';
    }
  };

  return (
    <div 
      onClick={onClick}
      className={`glass-card relative p-4 cursor-pointer transition-all duration-300 group ${
        isSelected ? 'bg-white/5 border-white/20' : 'hover:bg-white/2'
      }`}
    >
      <div className="flex items-start justify-between mb-4">
        <div>
           <h4 className="text-sm font-black tracking-widest text-white/50 uppercase bg-white/2 px-2.5 py-1 rounded leading-none">
             {node.id.split('_')[1]}
           </h4>
           <div className="text-[9px] uppercase font-black tracking-widest text-white/30 mt-1 ml-0.5">
             {tier.replace('_', ' ')}
           </div>
        </div>
        <div className={`px-2.5 py-1 rounded-full text-[10px] font-black tracking-widest uppercase border ${getVerdictStyles()}`}>
           {verdict} {amount > 0 ? `${amount.toFixed(1)}kwh` : ''}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Compact SoC Ring */}
        <div className="relative w-14 h-14">
            <svg viewBox="0 0 36 36" className="w-full h-full rotate-[-90deg]">
                <circle cx="18" cy="18" r="16" fill="none" stroke="currentColor" strokeWidth="3" className="text-white/5" />
                <circle 
                    cx="18" cy="18" r="16" fill="none" stroke="currentColor" strokeWidth="3" 
                    strokeDasharray="100 100" strokeDashoffset={100 - soc}
                    className={`transition-all duration-1000 ease-in-out ${
                        soc < 20 ? 'text-rose-500' : soc < 50 ? 'text-amber-500' : 'text-emerald-500'
                    }`}
                />
            </svg>
              <div className="absolute inset-0 flex items-center justify-center text-[11px] font-mono font-bold text-white/90">
                {soc.toFixed(0)}%
            </div>
        </div>

            <div className="flex-1 grid grid-cols-2 gap-3">
            <div className="flex flex-col">
                <span className="text-[10px] uppercase font-bold text-white/30 flex items-center gap-1"><Sun size={9} /> Solar</span>
                <span className="text-[14px] font-mono font-bold text-emerald-400">{(node.solar || 0).toFixed(2)}</span>
            </div>
            <div className="flex flex-col">
                <span className="text-[10px] uppercase font-bold text-white/30 flex items-center gap-1"><Zap size={9} /> Load</span>
                <span className="text-[14px] font-mono font-bold text-rose-400">{(node.load || 0).toFixed(2)}</span>
            </div>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-white/5 grid grid-cols-2 gap-x-3 gap-y-2">
        <div className="flex flex-col">
          <span className="text-[9px] uppercase font-bold text-white/25">Battery Cap</span>
          <span className="text-[11px] font-mono font-bold text-indigo-300">{batteryCapacity.toFixed(1)} kWh</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase font-bold text-white/25">Voltage</span>
          <span className="text-[11px] font-mono font-bold text-sky-300">{voltage.toFixed(1)} V</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase font-bold text-white/25">Battery Pwr</span>
          <span className={`text-[11px] font-mono font-bold ${batteryPower >= 0 ? 'text-emerald-300' : 'text-amber-300'}`}>
            {batteryPower >= 0 ? '+' : ''}{batteryPower.toFixed(2)} kW
          </span>
        </div>
        <div className="flex flex-col">
          <span className="text-[9px] uppercase font-bold text-white/25">Grid I/O</span>
          <span className="text-[11px] font-mono font-bold text-white/70">
            {gridImport.toFixed(2)} / {gridExport.toFixed(2)}
          </span>
        </div>
      </div>

      {isSelected && (
          <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-white/40 to-transparent" />
      )}
    </div>
  );
};

export default HouseholdCard;
