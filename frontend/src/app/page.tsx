"use client";

import * as React from "react";
import { Sidebar } from "@/components/sidebar";
import { Topbar } from "@/components/topbar";
import { ChatFeed } from "@/components/chat/chat-feed";
import { Composer } from "@/components/chat/composer";
import { SettingsDialog } from "@/components/settings-dialog";
import { AppSettings, ConnectionStatus, Message, KnowledgeDocument } from "@/lib/types";
import { checkBackendStatus, askQuestion, deleteConversation, DEFAULT_DOCUMENTS } from "@/lib/api";
import { UploadCloud } from "lucide-react";
import { toast } from "sonner";

export default function DocentPage() {
  const [isClient, setIsClient] = React.useState(false);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [sidebarOpenMobile, setSidebarOpenMobile] = React.useState(false);
  const [isDragging, setIsDragging] = React.useState(false);
  const [isTyping, setIsTyping] = React.useState(false);
  const [initialPrompt, setInitialPrompt] = React.useState("");

  const [settings, setSettings] = React.useState<AppSettings>({
    baseUrl: "/api/backend",
    sessionId: "default",
    token: "",
    demoMode: false,
  });

  const [connectionStatus, setConnectionStatus] = React.useState<ConnectionStatus>("checking");
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [documents] = React.useState<KnowledgeDocument[]>(DEFAULT_DOCUMENTS);

  // Load saved settings from localStorage on client mount
  React.useEffect(() => {
    setIsClient(true);
    const storedBaseUrl = localStorage.getItem("docent_base_url");
    const savedBaseUrl = !storedBaseUrl || /^https?:\/\/(localhost|127\.0\.0\.1):8000\/?$/.test(storedBaseUrl)
      ? "/api/backend"
      : storedBaseUrl;
    if (savedBaseUrl !== storedBaseUrl) {
      localStorage.setItem("docent_base_url", savedBaseUrl);
    }
    const savedSessionId = localStorage.getItem("docent_session_id") || `session_${Math.random().toString(36).substring(2, 9)}`;
    const savedToken = localStorage.getItem("docent_token") || "";
    const savedDemoMode = localStorage.getItem("docent_demo_mode") === "true";

    const loadedSettings: AppSettings = {
      baseUrl: savedBaseUrl,
      sessionId: savedSessionId,
      token: savedToken,
      demoMode: savedDemoMode,
    };

    setSettings(loadedSettings);
  }, []);

  // Poll backend health check
  const refreshHealth = React.useCallback(async () => {
    if (settings.demoMode) {
      setConnectionStatus("authenticated");
      return;
    }
    const status = await checkBackendStatus(settings.baseUrl, settings.token);
    setConnectionStatus(status);
  }, [settings.baseUrl, settings.token, settings.demoMode]);

  React.useEffect(() => {
    if (!isClient) return;
    refreshHealth();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, [isClient, refreshHealth]);

  // Handle saving settings
  const handleSaveSettings = (updated: AppSettings) => {
    setSettings(updated);
    localStorage.setItem("docent_base_url", updated.baseUrl);
    localStorage.setItem("docent_session_id", updated.sessionId);
    localStorage.setItem("docent_token", updated.token);
    localStorage.setItem("docent_demo_mode", String(updated.demoMode));
    refreshHealth();
  };

  // Handle new conversation
  const handleNewChat = () => {
    const newSession = `session_${Math.random().toString(36).substring(2, 9)}`;
    setSettings((prev) => ({ ...prev, sessionId: newSession }));
    localStorage.setItem("docent_session_id", newSession);
    setMessages([]);
    toast.info("Started new conversation", { description: `Session: ${newSession}` });
  };

  // Handle clear chat
  const handleClearChat = async () => {
    const sessionToDelete = settings.sessionId;
    if (!sessionToDelete || messages.length === 0) {
      setMessages([]);
      return;
    }

    try {
      if (!settings.demoMode) {
        await deleteConversation(settings.baseUrl, settings.token, sessionToDelete);
      }
      setMessages([]);
      toast.success("Conversation deleted from the database");
    } catch (error) {
      console.error("Failed to delete conversation", error);
      setMessages([]);
      toast.error("Conversation deleted locally, but database delete failed");
    }
  };

  // Handle sending question
  const handleSendMessage = async (text: string) => {
    if (!settings.token && !settings.demoMode) {
      setSettingsOpen(true);
      toast.warning("Sign-in required", {
        description: "Configure your bearer token or enable Simulation Demo Mode in settings.",
      });
      return;
    }

    const userMessage: Message = {
      id: `usr-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setIsTyping(true);

    try {
      const response = await askQuestion({
        baseUrl: settings.baseUrl,
        token: settings.token,
        sessionId: settings.sessionId,
        message: text,
        history: newHistory.map((m) => ({ role: m.role, content: m.content })),
        demoMode: settings.demoMode,
      });

      const assistantMessage: Message = {
        id: `asst-${Date.now()}`,
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: unknown) {
      const errorCode = err instanceof Error ? err.message : "";
      let errorMessage = "Could not reach the backend service.";
      if (errorCode === "AUTHENTICATION_FAILED") {
        errorMessage = "Your bearer session token has expired or is invalid. Open settings to update.";
        setConnectionStatus("invalid_token");
      } else if (errorCode.startsWith("SERVER_ERROR_")) {
        const serverError = errorCode.slice("SERVER_ERROR_".length);
        const separatorIndex = serverError.indexOf(":");
        const status = separatorIndex === -1 ? serverError : serverError.slice(0, separatorIndex);
        const detail = separatorIndex === -1 ? "" : serverError.slice(separatorIndex + 1);
        errorMessage = detail
          ? `FastAPI returned HTTP ${status}: ${detail}`
          : `FastAPI returned HTTP ${status}. Check the backend logs for the processing error.`;
        setConnectionStatus("authenticated");
      } else {
        errorMessage = `Could not connect to FastAPI at ${settings.baseUrl}. Check that the backend server is running with CORS enabled.`;
        setConnectionStatus("offline");
      }

      const errorMsg: Message = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: errorMessage,
        timestamp: new Date().toISOString(),
        isError: true,
      };

      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  // Drag and drop overlay handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    toast.info("Knowledge Base Ingestion", {
      description: "Documents are managed server-side by the tenant repository.",
    });
  };

  const backendHost = settings.baseUrl.replace(/^https?:\/\//, "");

  if (!isClient) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-[#15181c] text-[#989b9f]">
        <div className="font-serif text-lg tracking-wider animate-pulse">Loading Docent…</div>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#15181c]">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex h-full">
        <Sidebar
          documents={documents}
          connectionStatus={connectionStatus}
          demoMode={settings.demoMode}
          onNewChat={handleNewChat}
          onOpenSettings={() => setSettingsOpen(true)}
        />
      </div>

      {/* Mobile Drawer Overlay */}
      {sidebarOpenMobile && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-xs"
            onClick={() => setSidebarOpenMobile(false)}
          />
          <div className="relative z-50 h-full">
            <Sidebar
              documents={documents}
              connectionStatus={connectionStatus}
              demoMode={settings.demoMode}
              onNewChat={() => {
                handleNewChat();
                setSidebarOpenMobile(false);
              }}
              onOpenSettings={() => {
                setSettingsOpen(true);
                setSidebarOpenMobile(false);
              }}
            />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <main
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="relative flex-1 flex flex-col min-w-0 h-full bg-[#15181c]"
      >
        {/* Topbar */}
        <Topbar
          documentCount={documents.length}
          sessionId={settings.sessionId}
          onClearChat={handleClearChat}
          onToggleSidebar={() => setSidebarOpenMobile(true)}
        />

        {/* Chat Feed */}
        <ChatFeed
          messages={messages}
          isTyping={isTyping}
          onSelectHint={(hint) => setInitialPrompt(hint)}
          onRetry={(lastPrompt) => handleSendMessage(lastPrompt)}
        />

        {/* Composer */}
        <Composer
          onSendMessage={handleSendMessage}
          disabled={isTyping}
          backendHost={backendHost}
          initialValue={initialPrompt}
          onClearInitialValue={() => setInitialPrompt("")}
        />

        {/* Full Viewport Drag-and-Drop Overlay */}
        {isDragging && (
          <div className="absolute inset-4 z-50 rounded-2xl border-2 border-dashed border-[#c68a3d] bg-[#15181c]/90 backdrop-blur-xs flex flex-col items-center justify-center gap-3 pointer-events-none animate-in fade-in-50 duration-150">
            <div className="p-4 rounded-full bg-[#c68a3d]/15 text-[#c68a3d]">
              <UploadCloud className="w-10 h-10 stroke-[1.5]" />
            </div>
            <div className="font-serif text-lg font-semibold text-[#e9e6e0]">
              Index into Knowledge Base
            </div>
            <div className="text-xs text-[#989b9f] max-w-sm text-center">
              Release files to submit them to the connected tenant ingestion queue.
            </div>
          </div>
        )}
      </main>

      {/* Settings Modal */}
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        settings={settings}
        onSaveSettings={handleSaveSettings}
        status={connectionStatus}
        onStatusChange={setConnectionStatus}
      />
    </div>
  );
}
