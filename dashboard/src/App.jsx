import React from 'react';
import { MicrogridProvider, useMicrogrid } from './context/MicrogridContext';
import CityMap from './components/CityMap';
import CityDashboard from './components/CityDashboard';
import { Activity, ShieldCheck, Cpu, Database, Play, Pause } from 'lucide-react';
import honeybeeLogo from './assets/honeybee_logo.png';

const DashboardContent = () => {
  const { 
    isConnected, 
    mqttConnected, 
    traceMqttEnabled, 
    serviceHealth, 
    activeCity, 
    setActiveCity, 
    simState, 
    setSimState 
  } = useMicrogrid();

  const HealthChip = ({ label, up }) => (
    <div className={`flex items-center gap-2 px-2.5 py-1 rounded-md border ${up ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${up ? 'bg-emerald-500 status-pulse' : 'bg-rose-500'}`} />
      <span className="text-[10px] font-black uppercase tracking-widest">{label}</span>
    </div>
  );

  return (
    <div className="flex-1 flex flex-col bg-[#06080d]">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-black/40 backdrop-blur-md z-20">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-xl bg-black/50 flex items-center justify-center shadow-2xl shadow-white/5 border border-white/10 overflow-hidden">
            <img 
              src={honeybeeLogo} 
              alt="Honeybee Logo" 
              className="w-full h-full object-contain scale-[1.8]" 
            />
          </div>
          <div>
            <h1 className="text-2xl font-black italic tracking-tighter uppercase leading-none text-white">Honeybee</h1>
            <p className="text-[10px] text-white/50 uppercase font-bold tracking-[0.2em] mt-2 flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${mqttConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.5)]'}`} /> Microgrid System Simulation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Simulation Control */}
          <div className="flex items-center gap-2 mr-4 bg-white/5 p-1 rounded-lg border border-white/10">
            <button 
                onClick={() => setSimState(simState === 'running' ? 'paused' : 'running')}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-md text-[10px] font-black uppercase tracking-widest transition-all ${simState === 'running' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30' : 'bg-emerald-500 text-black'}`}
            >
                {simState === 'running' ? <Pause size={12} fill="currentColor" /> : <Play size={12} fill="currentColor" />}
                {simState === 'running' ? 'Pause Sim' : 'Start Simulation'}
            </button>
          </div>

          <div className="hidden md:flex flex-col items-end">
            <span className="text-[10px] text-white/40 uppercase font-black tracking-tighter">Cluster Connectivity</span>
            <span className="text-sm font-mono text-white/80">75 Nodes Synchronized</span>
          </div>
          <div className="hidden xl:flex items-center gap-2">
            <HealthChip label="API" up={serviceHealth.api === 'up' && isConnected} />
            <HealthChip label="Marketplace" up={serviceHealth.marketplace === 'up'} />
            <HealthChip label="Trace MQTT" up={traceMqttEnabled ? mqttConnected : true} />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex">
        {activeCity ? (
          <CityDashboard cityId={activeCity} onBack={() => setActiveCity(null)} />
        ) : (
          <div className="flex-1 relative bg-[#06080d]">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(16,185,129,0.02),transparent)] pointer-events-none"></div>
            <CityMap onCitySelect={(cityId) => setActiveCity(cityId)} />
          </div>
        )}
      </main>

      {/* Footer Info-bar */}
      <footer className="px-6 py-2 border-t border-white/5 bg-black/40 flex items-center justify-between text-[10px] font-mono text-white/20 uppercase tracking-[0.2em] z-20">
        <div className="flex items-center gap-4">
          <span>&copy; 2026 Honeybee Microgrid System</span>
          <span className="text-white/5">/</span>
          <span className="flex items-center gap-1.5"><Cpu size={10} /> Strategic AI: Gemini 2.5 Flash Lite</span>
        </div>
        <div className="flex items-center gap-6">
           <span className="flex items-center gap-2 text-indigo-500/60"><Database size={10} /> 75 Regional Databases</span>
           <span className={`${traceMqttEnabled ? (mqttConnected ? 'text-emerald-500/40' : 'text-rose-500/40') : 'text-white/20'}`}>
             {traceMqttEnabled ? (mqttConnected ? 'Trace MQTT: Connected' : 'Trace MQTT: Reconnecting') : 'Trace MQTT: Disabled'}
           </span>
        </div>
      </footer>
    </div>
  );
};

const App = () => (
  <MicrogridProvider>
    <DashboardContent />
  </MicrogridProvider>
);

export default App;
