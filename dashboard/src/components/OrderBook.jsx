import React from 'react';

const OrderBook = ({ pending_buy_orders = [], pending_sell_orders = [] }) => {
  // Sort buys descending (highest price first)
  const sortedBuys = [...pending_buy_orders].sort((a, b) => b.price_per_kwh - a.price_per_kwh).slice(0, 8);
  // Sort sells ascending (lowest price first)
  const sortedSells = [...pending_sell_orders].sort((a, b) => a.price_per_kwh - b.price_per_kwh).slice(0, 8);

  const maxVolume = Math.max(
    ...sortedBuys.map(o => o.remaining_kwh),
    ...sortedSells.map(o => o.remaining_kwh),
    1
  );

  return (
    <div className="grid grid-cols-2 gap-4">
      {/* Bids (BUY) */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-2 px-2 text-[10px] font-black uppercase tracking-widest text-white/30">
          <span>Bid (Buy)</span>
          <span>Qty</span>
          <span>Price</span>
        </div>
        <div className="space-y-1">
          {sortedBuys.length > 0 ? sortedBuys.map((order, idx) => (
            <div key={idx} className="relative h-6 flex items-center justify-between px-2 bg-blue-500/5 rounded border border-blue-500/10 overflow-hidden">
              <div 
                className="absolute right-0 top-0 bottom-0 bg-blue-500/10 transition-all duration-1000" 
                style={{ width: `${(order.remaining_kwh / maxVolume) * 100}%` }}
              />
              <span className="relative z-10 text-[9px] font-mono text-blue-400 font-bold">{order.node_id.split('_')[1]}</span>
              <span className="relative z-10 text-[9px] font-mono text-white/60">{order.remaining_kwh.toFixed(2)}</span>
              <span className="relative z-10 text-[10px] font-mono text-blue-400 font-black">₹{order.price_per_kwh.toFixed(2)}</span>
            </div>
          )) : (
            <div className="h-20 flex items-center justify-center border border-dashed border-white/5 rounded">
              <span className="text-[10px] text-white/10 uppercase font-bold tracking-widest">No Bids</span>
            </div>
          )}
        </div>
      </div>

      {/* Asks (SELL) */}
      <div className="flex flex-col">
        <div className="flex items-center justify-between mb-2 px-2 text-[10px] font-black uppercase tracking-widest text-white/30">
          <span>Price</span>
          <span>Qty</span>
          <span>Ask (Sell)</span>
        </div>
        <div className="space-y-1">
          {sortedSells.length > 0 ? sortedSells.map((order, idx) => (
            <div key={idx} className="relative h-6 flex items-center justify-between px-2 bg-emerald-500/5 rounded border border-emerald-500/10 overflow-hidden">
              <div 
                className="absolute left-0 top-0 bottom-0 bg-emerald-500/10 transition-all duration-1000" 
                style={{ width: `${(order.remaining_kwh / maxVolume) * 100}%` }}
              />
              <span className="relative z-10 text-[10px] font-mono text-emerald-400 font-black">₹{order.price_per_kwh.toFixed(2)}</span>
              <span className="relative z-10 text-[9px] font-mono text-white/60">{order.remaining_kwh.toFixed(2)}</span>
              <span className="relative z-10 text-[9px] font-mono text-emerald-400 font-bold">{order.node_id.split('_')[1]}</span>
            </div>
          )) : (
            <div className="h-20 flex items-center justify-center border border-dashed border-white/5 rounded">
              <span className="text-[10px] text-white/10 uppercase font-bold tracking-widest">No Asks</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default OrderBook;
