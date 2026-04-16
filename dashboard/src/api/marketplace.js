import { fetchJSON, createEventSource } from './client';

export function getMarketOrders(cityId) {
  return fetchJSON('/api/market/orders', { params: { city: cityId || undefined } });
}

export function getMarketStats(cityId) {
  return fetchJSON('/api/market/stats', { params: { city: cityId || undefined } });
}

export function getRecentTrades(cityId, limit = 50) {
  return fetchJSON('/api/market/trades', {
    params: { limit, city: cityId || undefined },
  });
}

export function getWallets(nodeIds) {
  return fetchJSON('/api/market/wallets', {
    params: { node_ids: nodeIds.join(',') },
  });
}

export function getMarketLeaderboard(limit = 15) {
  return fetchJSON('/api/market/leaderboard', { params: { limit } });
}

export function subscribeMarketFeed() {
  return createEventSource('/api/market/feed');
}
