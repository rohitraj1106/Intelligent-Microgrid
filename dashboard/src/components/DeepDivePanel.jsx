import React, { useState, useEffect } from 'react';
import { useMicrogrid } from '../context/MicrogridContext';
import { Zap, TrendingUp, Activity, Cpu, ShieldCheck } from 'lucide-react';
import ForecastChart from './ForecastChart';

const DeepDivePanel = () => {
  const { selectedNodeId, traceData } = useMicrogrid();
  const [typedReasoning, setTypedReasoning] = useState("");
  
  // Typing animation for LLM reasoning
  useEffect(() => {
    const reasoningText = traceData.agent?.reasoning?.trim();
    const shouldType = Boolean(reasoningText) && !reasoningText.toLowerCase().includes('waiting');
    if (!shouldType) {
      setTypedReasoning("");
      return;
    }

    setTypedReasoning("");
    let i = 0;
    const interval = setInterval(() => {
      setTypedReasoning(prev => prev + reasoningText.charAt(i));
      i++;
      if (i >= reasoningText.length) clearInterval(interval);
    }, 15);
    return () => clearInterval(interval);
  }, [traceData.agent?.reasoning]);

  const telemetry = traceData.telemetry?.output || {};
  const orchestrator = traceData.orchestrator?.output || {};
  const forecast = traceData.forecast || null;

  // Extract hour from simulation time for the clock
  const simTime = telemetry.timestamp ? new Date(telemetry.timestamp) : new Date();
  const timeStr = simTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="flex flex-col gap-6 p-6 overflow-y-auto h-full border-l border-white/5 scrollbar-hide bg-slate-950/20">
      <div className="flex flex-col pb-4 border-b border-white/5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex flex-col">
            <h2 className="text-3xl font-black italic tracking-tighter uppercase text-white/95 leading-none flex items-center gap-3">
               {selectedNodeId}
               {traceData.agent?.reasoning?.includes('[SPECULATIVE]') ? (
                 <span className="px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-[9px] font-black text-amber-400 tracking-[0.2em]">
                   SHADOW AI
                 </span>
               ) : traceData.agent?.reasoning?.includes('[SIMULATED]') ? (
                 <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[9px] font-black text-white/30 tracking-[0.2em]">
                   SIMULATED
                 </span>
               ) : traceData.agent?.reasoning?.includes('[REFINED]') ? (
                 <span className="px-2 py-0.5 rounded bg-indigo-500/20 border border-indigo-500/40 text-[9px] font-black text-indigo-400 tracking-[0.2em] animate-pulse">
                   GEMMA 4 26B
                 </span>
               ) : null}
            </h2>
            <div className="flex items-center gap-2 mt-1">
               <Zap size={10} className="text-emerald-400 fill-emerald-400" />
               <span className="text-[10px] font-bold text-white/40 tracking-[0.2em] uppercase">Core Sync: Active</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
             <div className="px-3 py-1 rounded bg-white/5 border border-white/10 text-[11px] font-mono font-bold text-emerald-400 shadow-inner">
                {timeStr}
             </div>
             <div className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest border shadow-lg transition-all duration-500 scale-90 origin-right ${
               orchestrator.fsm_state === 'P2P_TRADING' ? 'bg-amber-500/20 border-amber-500/40 text-amber-400 shadow-amber-500/10' :
               orchestrator.fsm_state === 'EMERGENCY' ? 'bg-rose-500/20 border-rose-500/40 text-rose-400 shadow-rose-500/10' :
               'bg-emerald-500/20 border-emerald-500/40 text-emerald-400 shadow-emerald-500/10'
             }`}>
               {orchestrator.fsm_state || "MONITORING"}
             </div>
          </div>
        </div>
        
        {traceData.agent?.output && traceData.agent.output.action !== 'THINKING' && (
          <div className="mt-2 p-4 rounded-xl bg-gradient-to-br from-white/10 to-transparent border border-white/10 flex items-center justify-between shadow-2xl relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-1 opacity-10 group-hover:opacity-100 transition-opacity">
               <TrendingUp size={40} className={`transform ${traceData.agent.output.action === 'SELL' ? 'rotate-180' : ''} text-white/20`} />
            </div>
            <div className="flex items-center gap-4 relative z-10">
              <div className={`w-12 h-12 rounded-lg flex items-center justify-center shadow-lg border-2 ${
                traceData.agent.output.action === 'BUY' ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' :
                traceData.agent.output.action === 'SELL' ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' :
                'bg-white/5 text-white/30 border-white/10'
              }`}>
                {traceData.agent.output.action === 'BUY' ? <TrendingUp size={24} /> : 
                 traceData.agent.output.action === 'SELL' ? <TrendingUp size={24} className="rotate-180" /> : 
                 <Activity size={24} />}
              </div>
              <div>
                <div className="text-[10px] font-black uppercase tracking-widest text-white/30 mb-0.5">AI Verdict</div>
                <div className="text-xl font-black tracking-tight text-white/90">
                   <span className={traceData.agent.output.action === 'BUY' ? 'text-blue-400' : traceData.agent.output.action === 'SELL' ? 'text-emerald-400' : 'text-white/60'}>
                    {traceData.agent.output.action}
                   </span>
                   {Number(traceData.agent.output.amount_kwh) > 0 && <span className="ml-2 opacity-80">{Number(traceData.agent.output.amount_kwh).toFixed(3)}kWh</span>}
                </div>
              </div>
            </div>
            {Number(traceData.agent.output.price_per_kwh) > 0 && (
              <div className="text-right">
                <div className="text-[10px] font-black uppercase tracking-widest text-white/30">Price</div>
                <div className="text-xl font-mono font-bold text-white/80">₹{Number(traceData.agent.output.price_per_kwh).toFixed(2)}</div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* NEW: Forecast Intelligence */}
      <div className="glass-card p-5">
         <div className="flex items-center gap-2 text-white/60 mb-2">
            <TrendingUp size={16} className="text-indigo-400" />
            <h4 className="text-[10px] font-black uppercase tracking-wider">24h Energy Vector (Predicted)</h4>
          </div>
          <ForecastChart data={forecast} />
      </div>

      {/* Grid: Live Telemetry */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 text-white/60 mb-4">
          <Cpu size={16} className="text-emerald-400" />
          <h4 className="text-[10px] font-black uppercase tracking-wider">Edge Intelligence</h4>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Voltage', value: `${(telemetry.voltage_v || 0).toFixed(1)}V`, color: 'text-blue-400' },
            { label: 'SoC', value: `${(telemetry.soc_pct || 0).toFixed(1)}%`, color: 'text-indigo-400' },
            { label: 'Load', value: `${(telemetry.power_load_kw || 0).toFixed(2)}kW`, color: 'text-rose-400' },
            { label: 'Solar', value: `${(telemetry.power_solar_kw || 0).toFixed(2)}kW`, color: 'text-emerald-400' }
          ].map((stat, i) => (
            <div key={i} className="flex flex-col p-3 rounded-xl bg-white/2 border border-white/5">
              <span className="text-[9px] text-white/30 uppercase font-bold mb-1">{stat.label}</span>
              <span className={`text-sm font-mono font-bold ${stat.color}`}>{stat.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Strategic Intelligence Trace */}
      <div className="glass-card flex-1 flex flex-col min-h-[300px] bg-slate-900/40 border-white/5 backdrop-blur-xl relative overflow-hidden">
        <div className="absolute inset-0 bg-grid-white/[0.02] pointer-events-none" />
        <div className="flex items-center gap-2 p-4 border-b border-white/5 relative z-10 bg-black/20">
          <Activity size={14} className="text-indigo-400" />
          <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/50">Reasoning Chain</h4>
        </div>
        <div className="p-6 font-mono text-[11px] overflow-y-auto flex-1 leading-relaxed text-slate-300 relative z-10 scrollbar-hide">
           {typedReasoning ? (
             <div className="space-y-6">
               <div className="relative">
                 <div className="absolute -left-3 top-0 bottom-0 w-[2px] bg-indigo-500/20" />
                 <p className="typing-cursor pl-3 italic text-indigo-100/90 drop-shadow-sm">{typedReasoning}</p>
               </div>
               {traceData.agent?.output && (
                 <div className="p-4 rounded-xl bg-black/60 border border-white/10 shadow-inner group/json">
                   <div className="flex items-center justify-between mb-3">
                      <div className="text-[9px] uppercase font-black text-white/20 tracking-widest group-hover/json:text-indigo-400/40 transition-colors">Inference Payload</div>
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                   </div>
                   <pre className="text-[10px] text-emerald-400/80 whitespace-pre-wrap leading-tight font-mono">{JSON.stringify(traceData.agent.output, null, 2)}</pre>
                 </div>
               )}
             </div>
           ) : (
             <div className="h-full flex items-center justify-center flex-col gap-4 opacity-30 py-12">
                <div className="w-10 h-10 rounded-full border-2 border-dashed border-indigo-500/50 animate-spin" />
                <p className="text-[10px] uppercase tracking-[0.4em] font-black ml-1 text-indigo-300">Awaiting Signal</p>
             </div>
           )}
        </div>
      </div>

      {/* Safety Governor */}
      <div className="glass-card p-5 bg-black/40">
          <div className="flex items-center gap-2 text-white/60 mb-4">
            <ShieldCheck size={16} className="text-emerald-400/60" />
            <h4 className="text-[10px] font-black uppercase tracking-wider">Safety Governor</h4>
          </div>
          <div className="grid grid-cols-1 gap-2">
             {[
               { id: 'reserve', label: 'Battery Reserve', status: telemetry.soc_pct > 10 ? 'PASS' : 'FAIL', context: '10% Min' },
               { id: 'strategy', label: 'Tactical Verdict', status: orchestrator.strategy_status || "WAITING", context: orchestrator.reason || "Analyzing..." },
             ].map((check, i) => (
               <div key={i} className="flex items-center justify-between p-3 rounded-xl bg-white/2 border border-white/5">
                 <div className="flex flex-col">
                   <span className="text-[11px] font-bold text-white/70 uppercase tracking-tight">{check.label}</span>
                   <span className="text-[9px] text-white/20 uppercase font-mono">{check.context}</span>
                 </div>
                 <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-widest uppercase ${
                   check.status === 'PASS' || check.status === 'ALLOWED' || check.status === 'COMPLETED' ? 'text-emerald-400' : 
                   check.status === 'FAIL' ? 'text-rose-400' : 'text-white/40'
                 }`}>
                   {check.status}
                 </span>
               </div>
             ))}
          </div>
      </div>
    </div>
  );
};

export default DeepDivePanel;
