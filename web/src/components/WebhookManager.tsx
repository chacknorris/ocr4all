import { useState, useEffect } from 'react';

interface Webhook {
  id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
  retry_count: number;
  timeout_seconds: number;
  created_at: string;
  updated_at: string;
}

interface WebhookDelivery {
  id: string;
  event_type: string;
  response_status: number | null;
  response_time_ms: number | null;
  attempt_count: number;
  success: boolean;
  error_message: string | null;
  created_at: string;
}

const API_BASE = 'http://localhost:8000/api/v1';

const WEBHOOK_EVENTS = [
  'document.uploaded',
  'document.processing',
  'document.processed',
  'document.failed',
  'document.deleted',
  'extraction.completed',
  'extraction.corrected',
  'batch.completed',
];

export default function WebhookManager() {
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [availableEvents, setAvailableEvents] = useState<string[]>(WEBHOOK_EVENTS);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedWebhook, setSelectedWebhook] = useState<Webhook | null>(null);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adminApiKey, setAdminApiKey] = useState('');

  // Form state
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    events: ['document.processed'] as string[],
    retry_count: 3,
    timeout_seconds: 30,
  });

  const headers = adminApiKey
    ? { 'X-API-Key': adminApiKey, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' };

  useEffect(() => {
    if (adminApiKey) {
      fetchWebhooks();
      fetchAvailableEvents();
    }
  }, [adminApiKey]);

  const fetchWebhooks = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/auth/webhooks`, { headers });
      if (!response.ok) throw new Error('Failed to fetch webhooks');
      const data = await response.json();
      setWebhooks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const fetchAvailableEvents = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/webhook-events`, { headers });
      if (response.ok) {
        const data = await response.json();
        setAvailableEvents(data.events);
      }
    } catch {
      // Use default events
    }
  };

  const createWebhook = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE}/auth/webhooks`, {
        method: 'POST',
        headers,
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create webhook');
      }

      setShowCreateForm(false);
      setFormData({
        name: '',
        url: '',
        events: ['document.processed'],
        retry_count: 3,
        timeout_seconds: 30,
      });
      fetchWebhooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const toggleWebhook = async (webhookId: string) => {
    try {
      const response = await fetch(`${API_BASE}/auth/webhooks/${webhookId}/toggle`, {
        method: 'POST',
        headers,
      });
      if (!response.ok) throw new Error('Failed to toggle webhook');
      fetchWebhooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const deleteWebhook = async (webhookId: string) => {
    if (!confirm('Are you sure you want to delete this webhook?')) return;

    try {
      const response = await fetch(`${API_BASE}/auth/webhooks/${webhookId}`, {
        method: 'DELETE',
        headers,
      });
      if (!response.ok) throw new Error('Failed to delete webhook');
      fetchWebhooks();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const fetchDeliveries = async (webhook: Webhook) => {
    try {
      setSelectedWebhook(webhook);
      const response = await fetch(
        `${API_BASE}/auth/webhooks/${webhook.id}/deliveries`,
        { headers }
      );
      if (!response.ok) throw new Error('Failed to fetch deliveries');
      const data = await response.json();
      setDeliveries(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const retryDelivery = async (deliveryId: string) => {
    try {
      const response = await fetch(
        `${API_BASE}/auth/webhooks/deliveries/${deliveryId}/retry`,
        { method: 'POST', headers }
      );
      if (!response.ok) throw new Error('Failed to retry delivery');
      if (selectedWebhook) {
        fetchDeliveries(selectedWebhook);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const toggleEvent = (event: string) => {
    setFormData((prev) => ({
      ...prev,
      events: prev.events.includes(event)
        ? prev.events.filter((e) => e !== event)
        : [...prev.events, event],
    }));
  };

  if (!adminApiKey) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Webhook Management</h2>
        <p className="text-gray-600 mb-4">
          Enter an admin API key to manage webhooks.
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
      {error && (
        <div className="p-3 bg-red-50 text-red-700 rounded-lg">{error}</div>
      )}

      {/* Webhooks List */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Webhooks</h2>
          <button
            onClick={() => setShowCreateForm(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Create Webhook
          </button>
        </div>

        {loading && !webhooks.length ? (
          <p className="text-gray-500">Loading...</p>
        ) : webhooks.length === 0 ? (
          <p className="text-gray-500">No webhooks configured.</p>
        ) : (
          <div className="space-y-4">
            {webhooks.map((webhook) => (
              <div
                key={webhook.id}
                className="border rounded-lg p-4 hover:bg-gray-50"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-medium">{webhook.name}</h3>
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          webhook.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {webhook.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1 font-mono">
                      {webhook.url}
                    </p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {webhook.events.map((event) => (
                        <span
                          key={event}
                          className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded text-xs"
                        >
                          {event}
                        </span>
                      ))}
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                      Retries: {webhook.retry_count} | Timeout: {webhook.timeout_seconds}s
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => fetchDeliveries(webhook)}
                      className="text-blue-600 hover:underline text-sm"
                    >
                      Deliveries
                    </button>
                    <button
                      onClick={() => toggleWebhook(webhook.id)}
                      className="text-yellow-600 hover:underline text-sm"
                    >
                      {webhook.is_active ? 'Disable' : 'Enable'}
                    </button>
                    <button
                      onClick={() => deleteWebhook(webhook.id)}
                      className="text-red-600 hover:underline text-sm"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Webhook Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Create Webhook</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Name
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, name: e.target.value }))
                  }
                  placeholder="e.g., Production Notifications"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  URL
                </label>
                <input
                  type="url"
                  value={formData.url}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, url: e.target.value }))
                  }
                  placeholder="https://your-server.com/webhook"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Events
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {availableEvents.map((event) => (
                    <label key={event} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={formData.events.includes(event)}
                        onChange={() => toggleEvent(event)}
                        className="rounded"
                      />
                      <span className="text-sm">{event}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Retry Count
                  </label>
                  <input
                    type="number"
                    value={formData.retry_count}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        retry_count: parseInt(e.target.value),
                      }))
                    }
                    min={0}
                    max={10}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Timeout (seconds)
                  </label>
                  <input
                    type="number"
                    value={formData.timeout_seconds}
                    onChange={(e) =>
                      setFormData((prev) => ({
                        ...prev,
                        timeout_seconds: parseInt(e.target.value),
                      }))
                    }
                    min={5}
                    max={120}
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                </div>
              </div>
            </div>

            <div className="flex gap-2 mt-6">
              <button
                onClick={createWebhook}
                disabled={loading || !formData.name || !formData.url || formData.events.length === 0}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={() => setShowCreateForm(false)}
                className="px-4 py-2 bg-gray-200 rounded-lg hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Deliveries Modal */}
      {selectedWebhook && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">
                Deliveries: {selectedWebhook.name}
              </h3>
              <button
                onClick={() => setSelectedWebhook(null)}
                className="text-gray-500 hover:text-gray-700"
              >
                Close
              </button>
            </div>

            {deliveries.length === 0 ? (
              <p className="text-gray-500">No deliveries yet.</p>
            ) : (
              <div className="space-y-3">
                {deliveries.map((delivery) => (
                  <div
                    key={delivery.id}
                    className={`border rounded-lg p-3 ${
                      delivery.success ? 'border-green-200' : 'border-red-200'
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded text-xs ${
                              delivery.success
                                ? 'bg-green-100 text-green-800'
                                : 'bg-red-100 text-red-800'
                            }`}
                          >
                            {delivery.success ? 'Success' : 'Failed'}
                          </span>
                          <span className="text-sm font-medium">
                            {delivery.event_type}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-1">
                          {new Date(delivery.created_at).toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-600 mt-1">
                          Status: {delivery.response_status || 'N/A'} |
                          Time: {delivery.response_time_ms || 'N/A'}ms |
                          Attempts: {delivery.attempt_count}
                        </p>
                        {delivery.error_message && (
                          <p className="text-xs text-red-600 mt-1">
                            Error: {delivery.error_message}
                          </p>
                        )}
                      </div>
                      {!delivery.success && (
                        <button
                          onClick={() => retryDelivery(delivery.id)}
                          className="text-blue-600 hover:underline text-sm"
                        >
                          Retry
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
