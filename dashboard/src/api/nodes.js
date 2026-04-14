import { fetchJSON } from './client';

export function getNodeState(nodeId) {
  return fetchJSON(`/api/nodes/${nodeId}/state`);
}

export function getNodesHealth({ city, nodeIds } = {}) {
  return fetchJSON('/api/nodes/health', {
    params: {
      city: city || undefined,
      node_ids: nodeIds?.length ? nodeIds.join(',') : undefined,
    },
  });
}
