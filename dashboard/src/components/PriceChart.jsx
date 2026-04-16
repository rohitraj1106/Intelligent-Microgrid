import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const PriceChart = ({ trades = [] }) => {
  // Extract execution price history
  const data = [...trades].reverse().map((t, i) => ({
    name: i,
    price: t.price_per_kwh,
    time: new Date(t.executed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }));

  if (data.length === 0) {
    return (
      <div className="h-full flex items-center justify-center border border-dashed border-white/5 rounded-2xl bg-white/2 backdrop-blur hover:bg-white/5 transition-colors">
        <p className="text-[10px] font-black uppercase tracking-widest text-white/20">Awaiting Price Signal...</p>
      </div>
    );
  }

  return (
    <div className="h-full w-full relative group">
      <div className="absolute top-4 left-4 z-10">
        <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/30 mb-1 group-hover:text-indigo-400/60 transition-colors">Spot Price Index</h4>
        <div className="flex items-center gap-2">
            <span className="text-xl font-mono font-black text-indigo-400">₹{data[data.length-1].price.toFixed(2)}</span>
            <span className="text-[9px] font-bold text-white/20 uppercase tracking-widest">/ kWh</span>
        </div>
      </div>
      
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 80, right: 60, left: -20, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.03)" />
          <XAxis 
            dataKey="name" 
            hide={true}
          />
          <YAxis 
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9, fontWeight: 'bold' }}
            domain={[2, 10]}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '10px' }}
            itemStyle={{ fontWeight: 'bold' }}
            labelStyle={{ display: 'none' }}
          />
          <ReferenceLine y={8.50} stroke="#ef4444" strokeDasharray="3 3" opacity={0.3} label={{ position: 'right', value: 'Grid Buy', fill: '#ef4444', fontSize: 8, fontWeight: '900' }} />
          <ReferenceLine y={3.00} stroke="#10b981" strokeDasharray="3 3" opacity={0.3} label={{ position: 'right', value: 'Grid Sell', fill: '#10b981', fontSize: 8, fontWeight: '900' }} />
          <Line 
            type="monotone" 
            dataKey="price" 
            stroke="#6366f1" 
            strokeWidth={3}
            dot={{ r: 4, fill: '#6366f1', strokeWidth: 2, stroke: '#0f172a' }}
            activeDot={{ r: 6, fill: '#6366f1', strokeWidth: 0 }}
            animationDuration={1500}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default PriceChart;
