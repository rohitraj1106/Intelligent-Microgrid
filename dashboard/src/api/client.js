const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8100').replace(/\/$/, '');

async function fetchJSON(path, { params } = {}) {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        url.searchParams.set(k, String(v));
      }
    });
  }

  const response = await fetch(url.toString());
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${response.status}: ${body}`);
  }
  return response.json();
}

function createEventSource(path) {
  return new EventSource(`${API_BASE_URL}${path}`);
}

export { API_BASE_URL, fetchJSON, createEventSource };
