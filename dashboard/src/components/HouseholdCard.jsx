import React from 'react';
import { TrendingUp, Battery, Zap, Sun } from 'lucide-react';

const HouseholdCard = ({ node, isSelected, onClick, agentData }) => {
  const soc = node?.soc || 0;
  const verdict = agentData?.output?.action || 'HOLD';
  const amount = agentData?.output?.amount_kwh || 0;

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
           <h4 className="text-xs font-black tracking-widest text-white/40 uppercase bg-white/2 px-2 py-0.5 rounded leading-none">
             {node.id.split('_')[1]}
           </h4>
        </div>
        <div className={`px-2 py-0.5 rounded-full text-[8px] font-black tracking-widest uppercase border ${getVerdictStyles()}`}>
           {verdict} {amount > 0 ? `${amount.toFixed(1)}kwh` : ''}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Compact SoC Ring */}
        <div className="relative w-12 h-12">
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
            <div className="absolute inset-0 flex items-center justify-center text-[9px] font-mono font-bold text-white/90">
                {soc.toFixed(0)}%
            </div>
        </div>

        <div className="flex-1 grid grid-cols-2 gap-2">
            <div className="flex flex-col">
                <span className="text-[8px] uppercase font-bold text-white/20 flex items-center gap-1"><Sun size={8} /> Solar</span>
                <span className="text-[10px] font-mono font-bold text-emerald-400">{(node.solar || 0).toFixed(2)}</span>
            </div>
            <div className="flex flex-col">
                <span className="text-[8px] uppercase font-bold text-white/20 flex items-center gap-1"><Zap size={8} /> Load</span>
                <span className="text-[10px] font-mono font-bold text-rose-400">{(node.load || 0).toFixed(2)}</span>
            </div>
        </div>
      </div>

      {isSelected && (
          <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-transparent via-white/40 to-transparent" />
      )}
    </div>
  );
};

export default HouseholdCard;
