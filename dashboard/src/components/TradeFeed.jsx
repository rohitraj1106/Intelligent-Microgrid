import React from 'react';
import { ArrowRight, Zap } from 'lucide-react';

const TradeFeed = ({ trades = [] }) => {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-4 text-indigo-400">
        <Zap size={14} className="fill-indigo-400/20" />
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/50">Execution Ticker</h4>
      </div>
      
      <div className="flex-1 overflow-y-auto pr-2 scrollbar-hide space-y-2">
        {trades.length > 0 ? trades.map((trade, idx) => (
          <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-white/2 border border-white/5 group hover:bg-white/5 transition-colors">
            <div className="flex items-center gap-3">
              <span className="text-[10px] font-mono font-bold text-white/40">{trade.seller_node_id.split('_')[1]}</span>
              <ArrowRight size={10} className="text-white/10 group-hover:text-indigo-400 transition-colors" />
              <span className="text-[10px] font-mono font-bold text-indigo-400">{trade.buyer_node_id.split('_')[1]}</span>
            </div>
            <div className="flex flex-col items-end">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono font-black text-white/90">{trade.quantity_kwh.toFixed(2)} kWh</span>
                <span className="text-[10px] font-mono font-black text-emerald-400">@ ₹{trade.price_per_kwh.toFixed(2)}</span>
              </div>
              <span className="text-[8px] text-white/20 font-bold uppercase tracking-widest mt-0.5">
                {new Date(trade.executed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
          </div>
        )) : (
          <div className="h-full flex flex-col items-center justify-center opacity-10">
            <Zap size={40} className="mb-2" />
            <p className="text-[10px] uppercase font-black tracking-widest">Awaiting Trades...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradeFeed;
