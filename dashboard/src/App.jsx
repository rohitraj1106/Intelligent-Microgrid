import React from 'react';
import { MicrogridProvider, useMicrogrid } from './context/MicrogridContext';
import CityMap from './components/CityMap';
import CityDashboard from './components/CityDashboard';
import { Activity, ShieldCheck, Cpu, Database } from 'lucide-react';

const DashboardContent = () => {
  const { isConnected, mqttConnected, traceMqttEnabled, serviceHealth, activeCity, setActiveCity } = useMicrogrid();

  const HealthChip = ({ label, up }) => (
    <div className={`flex items-center gap-2 px-2.5 py-1 rounded-md border ${up ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-rose-500/10 border-rose-500/30 text-rose-400'}`}>
      <div className={`w-1.5 h-1.5 rounded-full ${up ? 'bg-emerald-500 status-pulse' : 'bg-rose-500'}`} />
      <span className="text-[10px] font-black uppercase tracking-widest">{label}</span>
    </div>
  );

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[#05070a]">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/5 bg-black/40 backdrop-blur-md z-20">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-indigo-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Activity className="text-white" size={20} />
          </div>
          <div>
            <h1 className="text-xl font-black italic tracking-tighter uppercase leading-none">Intelligent Microgrid</h1>
            <p className="text-[10px] text-white/30 uppercase font-bold tracking-widest mt-1.5 flex items-center gap-2">
              <ShieldCheck size={10} className="text-emerald-500/50" /> System Integrity Monitor v2.2
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6">
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
      <main className="flex-1 flex overflow-hidden">
        {activeCity ? (
          <CityDashboard cityId={activeCity} onBack={() => setActiveCity(null)} />
        ) : (
          <div className="flex-1 relative bg-[#06080d] overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_50%,rgba(16,185,129,0.02),transparent)] pointer-events-none"></div>
            <CityMap onCitySelect={(cityId) => setActiveCity(cityId)} />
          </div>
        )}
      </main>

      {/* Footer Info-bar */}
      <footer className="px-6 py-2 border-t border-white/5 bg-black/40 flex items-center justify-between text-[10px] font-mono text-white/20 uppercase tracking-[0.2em] z-20">
        <div className="flex items-center gap-4">
          <span>&copy; 2026 Microgrid Edge Network</span>
          <span className="text-white/5">/</span>
          <span className="flex items-center gap-1.5"><Cpu size={10} /> Strategic AI: Gemma 4 26B</span>
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
