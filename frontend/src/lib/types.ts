export interface Source {
  filename?: string;
  document?: string;
  page?: number | string;
  excerpt?: string;
  score?: number;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
  isError?: boolean;
}

export interface KnowledgeDocument {
  id: string;
  filename: string;
  status: 'ready' | 'indexing' | 'error';
  category?: string;
  size?: string;
}

export type ConnectionStatus = 'authenticated' | 'invalid_token' | 'sign_in_required' | 'offline' | 'checking';

export interface AppSettings {
  baseUrl: string;
  sessionId: string;
  token: string;
  demoMode: boolean;
}
