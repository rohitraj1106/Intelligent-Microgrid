import { createEventSource } from './client';

export function subscribeGatewayEvents() {
  return createEventSource('/api/market/feed');
}
