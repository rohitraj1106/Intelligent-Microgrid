import { API_BASE_URL } from './client';

const WRITE_API_KEY = import.meta.env.VITE_GATEWAY_WRITE_API_KEY || '';

export async function sendNodeCommand(payload) {
  if (!WRITE_API_KEY) {
    throw new Error('Missing VITE_GATEWAY_WRITE_API_KEY in dashboard environment');
  }

  const response = await fetch(`${API_BASE_URL}/api/orchestrator/commands`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': WRITE_API_KEY,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Command API ${response.status}: ${body}`);
  }

  return response.json();
}
