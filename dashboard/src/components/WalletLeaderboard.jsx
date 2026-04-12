import React from 'react';
import { Database, Wallet } from 'lucide-react';

const WalletLeaderboard = ({ wallets = [] }) => {
  const sortedWallets = [...wallets].sort((a, b) => b.balance_inr - a.balance_inr).slice(0, 15);
  const maxBalance = Math.max(...wallets.map(w => Math.abs(w.balance_inr)), 100);

  return (
    <div className="flex flex-col h-full bg-slate-900/10 p-6 rounded-2xl border border-white/5 backdrop-blur-xl relative overflow-hidden group">
      <div className="flex items-center gap-2 mb-6 text-indigo-400 relative z-10">
        <Wallet size={16} className="text-emerald-400" />
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/50">Market Leaderboard</h4>
      </div>
      
      <div className="flex-1 overflow-y-auto space-y-4 scrollbar-hide relative z-10 pr-2">
        {sortedWallets.length > 0 ? sortedWallets.map((wallet, idx) => (
          <div key={idx} className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-[9px] font-mono font-bold uppercase tracking-widest text-white/40">
              <span className="flex items-center gap-2 text-white/60">
                <span className="text-[10px] font-black italic tracking-tighter text-indigo-400 bg-indigo-500/10 px-1 py-0.5 rounded leading-none w-5 h-5 flex items-center justify-center">{(idx + 1).toString().padStart(2, '0')}</span>
                {wallet.node_id.split('_')[1]}
              </span>
              <span className={wallet.balance_inr >= 0 ? "text-emerald-400" : "text-rose-400"}>
                ₹{wallet.balance_inr.toFixed(2)}
              </span>
            </div>
            <div className="h-1.5 w-full bg-white/2 rounded-full overflow-hidden flex">
              <div 
                className={`h-full transition-all duration-1000 ease-out flex ${wallet.balance_inr >= 0 ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'}`}
                style={{ 
                  width: `${(Math.abs(wallet.balance_inr) / maxBalance) * 100}%`,
                  opacity: 0.8
                }}
              />
            </div>
            <div className="flex items-center justify-between text-[8px] text-white/20 uppercase font-black tracking-tighter">
              <span className="group-hover:text-emerald-400/40 transition-colors">In: ₹{wallet.total_earned.toFixed(0)}</span>
              <span className="group-hover:text-rose-400/40 transition-colors">Out: ₹{wallet.total_spent.toFixed(0)}</span>
            </div>
          </div>
        )) : (
          <div className="h-full flex items-center justify-center py-20 opacity-10">
            <Database size={40} />
          </div>
        )}
      </div>
      
      {/* Decorative Grid Backdrop */}
      <div className="absolute inset-0 bg-grid-white/[0.02] pointer-events-none" />
    </div>
  );
};

export default WalletLeaderboard;
