import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import {
  FileText,
  Upload as UploadIcon,
  LayoutDashboard,
  Settings2,
  Download,
  BarChart3,
  FolderTree,
  Key,
  Webhook
} from 'lucide-react';
import { UploadZone } from './components/UploadZone';
import { DocumentList } from './components/DocumentList';
import { DocumentDetail } from './components/DocumentDetail';
import { TemplateManager } from './components/TemplateManager';
import { ExportPanel } from './components/ExportPanel';
import { StatsOverview } from './components/StatsOverview';
import ApiKeyManager from './components/ApiKeyManager';
import WebhookManager from './components/WebhookManager';
import type { Document } from './types/document';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5000,
      retry: 1,
    },
  },
});

type View = 'dashboard' | 'documents' | 'upload' | 'templates' | 'export' | 'api-keys' | 'webhooks';

function AppContent() {
  const [currentView, setCurrentView] = useState<View>('dashboard');
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);

  const navItems: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <BarChart3 className="w-5 h-5" /> },
    { id: 'documents', label: 'Documentos', icon: <FileText className="w-5 h-5" /> },
    { id: 'upload', label: 'Subir', icon: <UploadIcon className="w-5 h-5" /> },
    { id: 'templates', label: 'Templates', icon: <Settings2 className="w-5 h-5" /> },
    { id: 'export', label: 'Exportar', icon: <Download className="w-5 h-5" /> },
    { id: 'api-keys', label: 'API Keys', icon: <Key className="w-5 h-5" /> },
    { id: 'webhooks', label: 'Webhooks', icon: <Webhook className="w-5 h-5" /> },
  ];

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Sidebar */}
      <aside className="fixed left-0 top-0 bottom-0 w-64 bg-slate-800 border-r border-slate-700 p-4 flex flex-col">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <h1 className="font-bold text-lg">OCR4All</h1>
            <p className="text-xs text-slate-400">Document Pipeline</p>
          </div>
        </div>

        <nav className="space-y-2 flex-1">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setCurrentView(item.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                currentView === item.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-300 hover:bg-slate-700'
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>

        <div className="text-xs text-slate-500 text-center pt-4 border-t border-slate-700">
          v4.0 - Etapa 4
        </div>
      </aside>

      {/* Main Content */}
      <main className="ml-64 p-8">
        {currentView === 'dashboard' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold">Dashboard</h2>
              <button
                onClick={() => setCurrentView('upload')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
              >
                <UploadIcon className="w-4 h-4" />
                Subir Documentos
              </button>
            </div>
            <StatsOverview />
          </div>
        )}

        {currentView === 'documents' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold">Documentos</h2>
              <button
                onClick={() => setCurrentView('upload')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
              >
                <UploadIcon className="w-4 h-4" />
                Subir
              </button>
            </div>
            <DocumentList onSelectDocument={setSelectedDocument} />
          </div>
        )}

        {currentView === 'upload' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <h2 className="text-2xl font-bold">Subir Documentos</h2>
            <UploadZone
              onUploadComplete={() => {
                queryClient.invalidateQueries({ queryKey: ['documents'] });
                queryClient.invalidateQueries({ queryKey: ['stats-overview'] });
              }}
            />
          </div>
        )}

        {currentView === 'templates' && <TemplateManager />}

        {currentView === 'export' && <ExportPanel />}

        {currentView === 'api-keys' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">API Keys</h2>
            <ApiKeyManager />
          </div>
        )}

        {currentView === 'webhooks' && (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Webhooks</h2>
            <WebhookManager />
          </div>
        )}
      </main>

      {/* Document Detail Modal */}
      {selectedDocument && (
        <DocumentDetail
          document={selectedDocument}
          onClose={() => setSelectedDocument(null)}
        />
      )}
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
