import { fetchJSON } from './client';

export function getSystemHealth() {
  return fetchJSON('/api/system/health');
}
