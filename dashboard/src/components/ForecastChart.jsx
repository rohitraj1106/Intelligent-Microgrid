import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

const ForecastChart = ({ data }) => {
  if (!data || !data.output) {
    return (
      <div className="h-48 flex items-center justify-center bg-white/2 rounded-xl border border-white/5 border-dashed">
        <p className="text-[10px] uppercase tracking-widest text-white/20">Awaiting Forecast Vector...</p>
      </div>
    );
  }

  const { load, solar, start_hour } = data.output;
  
  // Format data for Recharts
  const chartData = load.map((l, i) => {
    const hour = (start_hour + i) % 24;
    return {
      name: `${hour}:00`,
      load: l,
      solar: solar[i] || 0,
      net: (solar[i] || 0) - l
    };
  });

  return (
    <div className="w-full h-64 mt-4 relative">
      <div className="flex items-center justify-between mb-4 px-2">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]" />
            <span className="text-[9px] font-black uppercase tracking-tighter text-white/40">Load</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-[9px] font-black uppercase tracking-tighter text-white/40">Solar</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-0.5 bg-indigo-500/50" />
            <span className="text-[9px] font-black uppercase tracking-tighter text-white/20">Net Margin</span>
          </div>
        </div>
        <div className="text-[8px] font-black uppercase tracking-[0.2em] text-white/10 italic">
          24H Predictive Model v4.0
        </div>
      </div>

      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="colorLoad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorSolar" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
              <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorNet" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.1}/>
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.02)" />
          <XAxis 
            dataKey="name" 
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9, fontWeight: 'bold' }}
            interval={3}
          />
          <YAxis 
            axisLine={false}
            tickLine={false}
            tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 9, fontWeight: 'bold' }}
          />
          <Tooltip 
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', fontSize: '10px' }}
            itemStyle={{ fontWeight: 'bold', padding: '2px 0' }}
            cursor={{ stroke: 'rgba(255,255,255,0.1)', strokeWidth: 1 }}
          />
          <ReferenceLine y={0} stroke="rgba(255,255,255,0.05)" strokeWidth={1} />
          
          <Area 
            type="monotone" 
            dataKey="net" 
            stroke="transparent" 
            fillOpacity={1} 
            fill="url(#colorNet)" 
            animationDuration={1000}
          />
          
          <Area 
            type="monotone" 
            dataKey="load" 
            stroke="#f43f5e" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorLoad)" 
            strokeDasharray="4 4"
            animationDuration={1500}
          />
          <Area 
            type="monotone" 
            dataKey="solar" 
            stroke="#10b981" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorSolar)" 
            animationDuration={1500}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ForecastChart;
