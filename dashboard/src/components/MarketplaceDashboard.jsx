import React, { useState, useEffect, useRef } from 'react';
import OrderBook from './OrderBook';
import TradeFeed from './TradeFeed';
import WalletLeaderboard from './WalletLeaderboard';
import PriceChart from './PriceChart';
import { TrendingUp, Activity, Globe, ShieldCheck, Database, Zap } from 'lucide-react';
import {
  getMarketOrders,
  getMarketStats,
  getRecentTrades,
  getWallets,
  subscribeMarketFeed,
} from '../api/marketplace';

const MarketplaceDashboard = ({ cityId }) => {
  const [marketData, setMarketData] = useState({
    pending_buy_orders: [],
    pending_sell_orders: [],
    total_buy_volume_kwh: 0,
    total_sell_volume_kwh: 0,
    best_buy_price: 0,
    best_sell_price: 0
  });

  const [stats, setStats] = useState({
    total_trades: 0,
    total_volume_kwh: 0,
    average_price_per_kwh: 0,
    active_nodes: 0
  });

  const [recentTrades, setRecentTrades] = useState([]);
  const [wallets, setWallets] = useState([]);
  const [loading, setLoading] = useState(true);
  const lastRefreshRef = useRef(0);
  const refreshTimerRef = useRef(null);

  // Bootstrap data + live SSE updates for marketplace API
  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        const [ordersData, statsData, tradesData] = await Promise.all([
          getMarketOrders(cityId),
          getMarketStats(cityId),
          getRecentTrades(cityId, 50),
        ]);

        setMarketData(ordersData);
        setStats(statsData);
        setRecentTrades(tradesData);

        // BULK FETCH Wallets for city nodes (one call per city)
        const cityPrefix = cityId.toLowerCase();
        const nodeIds = Array.from({ length: 15 }, (_, i) => 
          `${cityPrefix}_${i.toString().padStart(2, '0')}`
        );
        const walletData = await getWallets(nodeIds);
        setWallets(walletData);

        setLoading(false);
      } catch (err) {
        console.error('Marketplace fetch error:', err);
      }
    };

    const scheduleRefresh = () => {
      const now = Date.now();
      if (now - lastRefreshRef.current < 1500) return;
      lastRefreshRef.current = now;
      if (refreshTimerRef.current) return;
      refreshTimerRef.current = setTimeout(() => {
        refreshTimerRef.current = null;
        fetchMarketData();
      }, 300);
    };

    fetchMarketData();
    const fallbackInterval = setInterval(fetchMarketData, 15000);

    const eventSource = subscribeMarketFeed();
    eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.buyer_node_id && payload.seller_node_id) {
          if (!cityId || payload.city === cityId) {
            setRecentTrades((prev) => [payload, ...prev].slice(0, 50));
          }
          scheduleRefresh();
          return;
        }
        if (payload.order_type) {
          if (!cityId || payload.city === cityId) {
            scheduleRefresh();
          }
        }
      } catch (err) {
        console.error('SSE parse error:', err);
      }
    };

    eventSource.onerror = () => {
      eventSource.close();
    };

    return () => {
      clearInterval(fallbackInterval);
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
      eventSource.close();
    };
  }, [cityId]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-[#0a0f1a]">
      {/* Top Stats Banner */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-8 border-b border-white/5 bg-black/20">
         {[
           { label: 'Network Depth', value: `${stats.active_nodes}/75`, detail: 'Active Strategic Nodes', icon: Globe, color: 'text-indigo-400' },
           { label: 'Accumulated Volume', value: `${stats.total_volume_kwh.toFixed(1)}kwh`, detail: `City Volume: ${cityId}`, icon: Activity, color: 'text-emerald-400' },
           { label: 'Avg P2P Price', value: `₹${(stats.average_price_per_kwh || 0).toFixed(2)}`, detail: 'Current Clearing Price', icon: TrendingUp, color: 'text-amber-400' },
           { label: 'Settled Trades', value: stats.total_trades, detail: 'Handshakes Optimized', icon: ShieldCheck, color: 'text-blue-400' }
         ].map((stat, i) => (
           <div key={i} className="glass-card p-6 flex flex-col relative group overflow-hidden transition-all duration-500 hover:bg-white/5">
              <div className="flex items-center justify-between mb-2">
                 <span className="text-[9px] font-black uppercase tracking-[0.4em] text-white/20 group-hover:text-white/40 transition-colors">{stat.label}</span>
                 <stat.icon size={16} className={`${stat.color} group-hover:scale-110 transition-transform`} />
              </div>
              <div className="text-2xl font-black tracking-tighter text-white/90 drop-shadow-lg leading-tight uppercase italic">{stat.value}</div>
              <div className="text-[8px] font-bold text-white/10 uppercase tracking-widest mt-1 opacity-100 transition-opacity">{stat.detail}</div>
              <div className="absolute top-0 right-0 p-1 opacity-5 group-hover:opacity-10 transition-opacity">
                <stat.icon size={48} className={stat.color} />
              </div>
           </div>
         ))}
      </div>

      {/* Main Grid Floor */}
      <div className="flex-1 flex overflow-hidden p-8 gap-8">
        {/* Left Side: Order Book & Price Analytics */}
        <div className="flex-[3] flex flex-col gap-8 min-w-0">
           <div className="glass-card p-6 flex-1 flex flex-col">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                   <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,1)]" />
                   <h3 className="text-xs font-black uppercase tracking-[0.3em] text-white/70">Central Order Book</h3>
                </div>
                <div className="px-3 py-1 rounded bg-white/5 border border-white/10 text-[9px] font-mono text-white/40">
                   {cityId} LIQUIDITY ZONE
                </div>
              </div>
              <OrderBook 
                pending_buy_orders={marketData.pending_buy_orders} 
                pending_sell_orders={marketData.pending_sell_orders} 
              />
           </div>

           <div className="glass-card p-0 flex-[1.4] relative overflow-hidden bg-slate-900/40 border-white/5 group">
              <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-indigo-500/50 to-transparent" />
              <PriceChart trades={recentTrades} />
              <div className="absolute bottom-4 right-4 flex items-center gap-4 text-[8px] font-black uppercase tracking-widest text-white/10">
                 <span className="flex items-center gap-1.5"><Database size={10} /> SSE Live Feed</span>
                 <span className="flex items-center gap-1.5 text-indigo-500/30"><Zap size={10} className="fill-indigo-500/10" /> V-Latency: &lt; 2ms</span>
              </div>
           </div>
        </div>

        {/* Right Side: Execution Ticker & Leaderboard */}
        <div className="flex-[1.6] flex flex-col gap-8 min-w-[340px]">
           <div className="glass-card flex-1 p-6 relative overflow-hidden bg-black/40 border-white/5 backdrop-blur-xl">
              <TradeFeed trades={recentTrades} />
           </div>
           <div className="flex-[1.2] min-h-[300px]">
              <WalletLeaderboard wallets={wallets} />
           </div>
        </div>
      </div>
    </div>
  );
};

export default MarketplaceDashboard;
