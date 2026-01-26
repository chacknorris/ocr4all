import { useState, useEffect } from 'react';

interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  rate_limit: number;
  created_at: string;
}

interface ApiKeyCreated extends ApiKey {
  api_key: string;
}

interface UsageStats {
  total_requests: number;
  requests_last_hour: number;
  requests_last_24h: number;
  avg_response_time_ms: number | null;
  error_rate: number;
}

const API_BASE = 'http://localhost:8000/api/v1';

export default function ApiKeyManager() {
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyScopes, setNewKeyScopes] = useState<string[]>(['read']);
  const [newKeyRateLimit, setNewKeyRateLimit] = useState(1000);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [selectedKeyUsage, setSelectedKeyUsage] = useState<{ id: string; stats: UsageStats } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adminApiKey, setAdminApiKey] = useState('');

  const headers = adminApiKey ? { 'X-API-Key': adminApiKey } : {};

  useEffect(() => {
    if (adminApiKey) {
      fetchApiKeys();
    }
  }, [adminApiKey]);

  const fetchApiKeys = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/auth/api-keys`, { headers });
      if (!response.ok) throw new Error('Failed to fetch API keys');
      const data = await response.json();
      setApiKeys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const createApiKey = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE}/auth/api-keys`, {
        method: 'POST',
        headers: {
          ...headers,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: newKeyName,
          scopes: newKeyScopes,
          rate_limit: newKeyRateLimit,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create API key');
      }

      const data: ApiKeyCreated = await response.json();
      setCreatedKey(data);
      setNewKeyName('');
      fetchApiKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const revokeApiKey = async (keyId: string) => {
    if (!confirm('Are you sure you want to revoke this API key?')) return;

    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/auth/api-keys/${keyId}`, {
        method: 'DELETE',
        headers,
      });

      if (!response.ok) throw new Error('Failed to revoke API key');
      fetchApiKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchUsageStats = async (keyId: string) => {
    try {
      const response = await fetch(`${API_BASE}/auth/api-keys/${keyId}/usage`, { headers });
      if (!response.ok) throw new Error('Failed to fetch usage stats');
      const stats: UsageStats = await response.json();
      setSelectedKeyUsage({ id: keyId, stats });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const toggleScope = (scope: string) => {
    setNewKeyScopes((prev) =>
      prev.includes(scope) ? prev.filter((s) => s !== scope) : [...prev, scope]
    );
  };

  if (!adminApiKey) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">API Key Management</h2>
        <p className="text-gray-600 mb-4">
          Enter an admin API key to manage organization API keys.
        </p>
        <input
          type="password"
          placeholder="Admin API Key"
          className="w-full px-3 py-2 border rounded-lg"
          value={adminApiKey}
          onChange={(e) => setAdminApiKey(e.target.value)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Create New Key */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Create API Key</h2>

        {error && (
          <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg">{error}</div>
        )}

        {createdKey && (
          <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="font-semibold text-green-800 mb-2">
              API Key Created Successfully!
            </p>
            <p className="text-sm text-green-700 mb-2">
              Copy this key now. You won't be able to see it again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 bg-white px-3 py-2 rounded border font-mono text-sm break-all">
                {createdKey.api_key}
              </code>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(createdKey.api_key);
                  alert('Copied to clipboard!');
                }}
                className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                Copy
              </button>
            </div>
            <button
              onClick={() => setCreatedKey(null)}
              className="mt-2 text-sm text-green-700 hover:underline"
            >
              Dismiss
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Key Name
            </label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g., Production API Key"
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rate Limit (requests/hour)
            </label>
            <input
              type="number"
              value={newKeyRateLimit}
              onChange={(e) => setNewKeyRateLimit(parseInt(e.target.value))}
              min={1}
              max={100000}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>
        </div>

        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Scopes
          </label>
          <div className="flex gap-4">
            {['read', 'write', 'admin'].map((scope) => (
              <label key={scope} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={newKeyScopes.includes(scope)}
                  onChange={() => toggleScope(scope)}
                  className="rounded"
                />
                <span className="capitalize">{scope}</span>
              </label>
            ))}
          </div>
        </div>

        <button
          onClick={createApiKey}
          disabled={loading || !newKeyName || newKeyScopes.length === 0}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Creating...' : 'Create API Key'}
        </button>
      </div>

      {/* API Keys List */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">API Keys</h2>

        {loading && !apiKeys.length ? (
          <p className="text-gray-500">Loading...</p>
        ) : apiKeys.length === 0 ? (
          <p className="text-gray-500">No API keys found.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3">Name</th>
                  <th className="text-left py-2 px-3">Prefix</th>
                  <th className="text-left py-2 px-3">Scopes</th>
                  <th className="text-left py-2 px-3">Rate Limit</th>
                  <th className="text-left py-2 px-3">Last Used</th>
                  <th className="text-left py-2 px-3">Status</th>
                  <th className="text-left py-2 px-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {apiKeys.map((key) => (
                  <tr key={key.id} className="border-b hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium">{key.name}</td>
                    <td className="py-2 px-3">
                      <code className="bg-gray-100 px-2 py-1 rounded text-sm">
                        {key.key_prefix}...
                      </code>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex gap-1">
                        {key.scopes.map((scope) => (
                          <span
                            key={scope}
                            className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs"
                          >
                            {scope}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-2 px-3">{key.rate_limit}/hr</td>
                    <td className="py-2 px-3 text-sm text-gray-600">
                      {key.last_used_at
                        ? new Date(key.last_used_at).toLocaleString()
                        : 'Never'}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          key.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {key.is_active ? 'Active' : 'Revoked'}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <div className="flex gap-2">
                        <button
                          onClick={() => fetchUsageStats(key.id)}
                          className="text-blue-600 hover:underline text-sm"
                        >
                          Usage
                        </button>
                        {key.is_active && (
                          <button
                            onClick={() => revokeApiKey(key.id)}
                            className="text-red-600 hover:underline text-sm"
                          >
                            Revoke
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Usage Stats Modal */}
      {selectedKeyUsage && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">API Key Usage</h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-50 p-3 rounded">
                <div className="text-2xl font-bold">
                  {selectedKeyUsage.stats.total_requests.toLocaleString()}
                </div>
                <div className="text-sm text-gray-600">Total Requests</div>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <div className="text-2xl font-bold">
                  {selectedKeyUsage.stats.requests_last_hour}
                </div>
                <div className="text-sm text-gray-600">Last Hour</div>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <div className="text-2xl font-bold">
                  {selectedKeyUsage.stats.requests_last_24h}
                </div>
                <div className="text-sm text-gray-600">Last 24h</div>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <div className="text-2xl font-bold">
                  {selectedKeyUsage.stats.avg_response_time_ms?.toFixed(0) || '-'} ms
                </div>
                <div className="text-sm text-gray-600">Avg Response Time</div>
              </div>
              <div className="bg-gray-50 p-3 rounded col-span-2">
                <div className="text-2xl font-bold">
                  {selectedKeyUsage.stats.error_rate.toFixed(2)}%
                </div>
                <div className="text-sm text-gray-600">Error Rate</div>
              </div>
            </div>

            <button
              onClick={() => setSelectedKeyUsage(null)}
              className="mt-4 w-full px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
