import React, { useState } from 'react';
import { useMicrogrid } from '../context/MicrogridContext';
import HouseholdCard from './HouseholdCard';
import DeepDivePanel from './DeepDivePanel';
import MarketplaceDashboard from './MarketplaceDashboard';
import { ArrowLeft, Cpu, Activity, ShieldCheck, Globe, ShoppingCart } from 'lucide-react';

const CityDashboard = ({ cityId, onBack }) => {
  const { nodes, selectedNodeId, setSelectedNodeId, allTraces } = useMicrogrid();
  const [activeView, setActiveView] = useState('intelligence'); // 'intelligence' | 'marketplace'
  
  // Filter nodes for this city
  const cityNodes = Object.keys(nodes)
    .filter(id => id.startsWith(cityId))
    .sort()
    .map(id => nodes[id]);

  // City-wide stats
  const activeTrades = Object.keys(allTraces.agent).filter(id => id.startsWith(cityId) && allTraces.agent[id]?.output?.action !== 'HOLD').length;
  const avgSoc = cityNodes.length > 0 ? cityNodes.reduce((acc, n) => acc + (n.soc || 0), 0) / cityNodes.length : 0;

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#06080d]">
      {/* City Sub-Header */}
      <div className="px-8 py-4 border-b border-white/5 bg-black/40 backdrop-blur-xl flex items-center justify-between z-30">
          <div className="flex items-center gap-6">
            <button 
              onClick={onBack}
              className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-white/60 hover:bg-white/10 hover:text-white transition-all group"
            >
              <ArrowLeft size={18} className="group-hover:-translate-x-0.5 transition-transform" />
            </button>
            <div>
              <div className="flex items-center gap-3">
                  <h2 className="text-2xl font-black italic tracking-tighter uppercase text-white/95 leading-none">{cityId} Subgrid</h2>
                  <div className="flex items-center p-1 bg-white/5 rounded-lg border border-white/10">
                    <button 
                      onClick={() => setActiveView('intelligence')}
                      className={`px-4 py-1.5 rounded-md text-[9px] font-black uppercase tracking-widest transition-all ${activeView === 'intelligence' ? 'bg-indigo-600 text-white shadow-lg' : 'text-white/30 hover:text-white/60'}`}
                    >
                      Node Intelligence
                    </button>
                    <button 
                      onClick={() => setActiveView('marketplace')}
                      className={`px-4 py-1.5 rounded-md text-[9px] font-black uppercase tracking-widest transition-all ${activeView === 'marketplace' ? 'bg-emerald-600 text-white shadow-lg' : 'text-white/30 hover:text-white/60'}`}
                    >
                      Energy Marketplace
                    </button>
                  </div>
              </div>
            </div>
          </div>

          <div className="flex gap-8">
            <div className="flex flex-col items-end">
                <span className="text-[9px] font-black text-white/20 uppercase tracking-widest">Region Status</span>
                <span className="text-sm font-mono font-bold text-emerald-400">ACTIVE SYNC</span>
            </div>
            <div className="flex flex-col items-end">
                <span className="text-[9px] font-black text-white/20 uppercase tracking-widest">Avg Subgrid SoC</span>
                <span className={`text-sm font-mono font-bold ${avgSoc < 30 ? 'text-rose-400' : 'text-emerald-400'}`}>{avgSoc.toFixed(1)}%</span>
            </div>
          </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {activeView === 'intelligence' ? (
          <>
            <div className="flex-[3] flex flex-col min-w-0">
              {/* Scrollable Household Grid */}
              <div className="flex-1 overflow-y-auto p-8 scrollbar-hide">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                      {cityNodes.map(node => (
                          <HouseholdCard 
                              key={node.id} 
                              node={node} 
                              isSelected={selectedNodeId === node.id}
                              onClick={() => setSelectedNodeId(node.id)}
                              agentData={allTraces.agent[node.id]}
                          />
                      ))}
                  </div>
              </div>
            </div>

            {/* Detail Panel */}
            <aside className="flex-[1.4] min-w-[380px] bg-black/30 backdrop-blur-3xl z-10 shadow-[-10px_0_40px_rgba(0,0,0,0.5)] border-l border-white/5">
              <DeepDivePanel />
            </aside>
          </>
        ) : (
          <MarketplaceDashboard cityId={cityId} />
        )}
      </div>
    </div>
  );
};

export default CityDashboard;
