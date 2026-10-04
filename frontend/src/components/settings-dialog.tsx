"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { AppSettings, ConnectionStatus } from "@/lib/types";
import { checkBackendStatus } from "@/lib/api";
import { RefreshCw, Eye, EyeOff, CheckCircle2, XCircle, AlertTriangle, Sparkles } from "lucide-react";
import { toast } from "sonner";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  settings: AppSettings;
  onSaveSettings: (settings: AppSettings) => void;
  status: ConnectionStatus;
  onStatusChange: (status: ConnectionStatus) => void;
}

export function SettingsDialog({
  open,
  onOpenChange,
  settings,
  onSaveSettings,
  status,
  onStatusChange,
}: SettingsDialogProps) {
  const [baseUrl, setBaseUrl] = React.useState(settings.baseUrl);
  const [sessionId, setSessionId] = React.useState(settings.sessionId);
  const [token, setToken] = React.useState(settings.token);
  const [demoMode, setDemoMode] = React.useState(settings.demoMode);
  const [showToken, setShowToken] = React.useState(false);
  const [testing, setTesting] = React.useState(false);

  // Sync state when opened
  React.useEffect(() => {
    if (open) {
      setBaseUrl(settings.baseUrl);
      setSessionId(settings.sessionId);
      setToken(settings.token);
      setDemoMode(settings.demoMode);
    }
  }, [open, settings]);

  const handleGenerateSession = () => {
    const newId = `session_${Math.random().toString(36).substring(2, 9)}`;
    setSessionId(newId);
  };

  const handleTestConnection = async () => {
    setTesting(true);
    try {
      const result = await checkBackendStatus(baseUrl, token);
      onStatusChange(result);
      if (result === "authenticated") {
        toast.success("Connected & Authenticated", {
          description: "FastAPI service is responding and token is valid.",
        });
      } else if (result === "invalid_token") {
        toast.error("Invalid Bearer Token", {
          description: "Backend reached, but token was rejected.",
        });
      } else if (result === "sign_in_required") {
        toast.warning("Sign-in Required", {
          description: "Backend reached, but bearer token is empty.",
        });
      } else {
        toast.error("Connection Failed", {
          description: `Unable to reach ${baseUrl}. Verify FastAPI is running.`,
        });
      }
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    const updated: AppSettings = {
      baseUrl: baseUrl.trim() || "/api/backend",
      sessionId: sessionId.trim() || "default",
      token: token.trim(),
      demoMode,
    };
    onSaveSettings(updated);
    toast.success("Settings saved successfully");
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md bg-[#1b1f24] border border-[#2e3339]">
        <DialogHeader>
          <DialogTitle>Backend Connection</DialogTitle>
          <DialogDescription>
            Configure your FastAPI customer-support endpoint and tenant authentication tokens.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Demo Mode Toggle */}
          <div className="p-3 rounded-lg bg-[#22262c] border border-[#2e3339] flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Sparkles className="w-4 h-4 text-[#c68a3d]" />
              <div>
                <div className="text-xs font-semibold text-[#e9e6e0]">
                  Offline / Demo Simulation Mode
                </div>
                <div className="text-[11px] text-[#989b9f]">
                  Return realistic RAG responses & verified citations if FastAPI is offline
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setDemoMode(!demoMode)}
              className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                demoMode ? "bg-[#c68a3d]" : "bg-[#333842]"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-[#15181c] shadow ring-0 transition duration-200 ease-in-out ${
                  demoMode ? "translate-x-4" : "translate-x-0"
                }`}
              />
            </button>
          </div>

          {/* Base URL */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#989b9f] uppercase tracking-wider">
              API Base URL
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="w-full px-3 py-2 rounded-md bg-[#1e2227] border border-[#2e3339] text-xs font-mono text-[#e9e6e0] focus:outline-none focus:border-[#c68a3d] transition-colors"
            />
          </div>

          {/* Session ID */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-[#989b9f] uppercase tracking-wider">
                Conversation Session ID
              </label>
              <button
                type="button"
                onClick={handleGenerateSession}
                className="text-[11px] text-[#c68a3d] hover:underline flex items-center gap-1 cursor-pointer"
              >
                <RefreshCw className="w-3 h-3" />
                <span>New Session</span>
              </button>
            </div>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              placeholder="default"
              className="w-full px-3 py-2 rounded-md bg-[#1e2227] border border-[#2e3339] text-xs font-mono text-[#e9e6e0] focus:outline-none focus:border-[#c68a3d] transition-colors"
            />
          </div>

          {/* Bearer Token */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#989b9f] uppercase tracking-wider">
              Bearer / Tenant Token
            </label>
            <div className="relative">
              <input
                type={showToken ? "text" : "password"}
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="e.g. demo-tenant"
                className="w-full pl-3 pr-9 py-2 rounded-md bg-[#1e2227] border border-[#2e3339] text-xs font-mono text-[#e9e6e0] focus:outline-none focus:border-[#c68a3d] transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="absolute right-2.5 top-2.5 text-[#989b9f] hover:text-[#e9e6e0] transition-colors"
              >
                {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <div className="text-[11px] text-[#6c7074]">
              Use <code className="text-[#989b9f]">demo-tenant</code> or your assigned tenant key.
            </div>
          </div>

          {/* Live Status Summary */}
          <div className="pt-2 flex items-center justify-between border-t border-[#26292f]">
            <div className="flex items-center gap-2 text-xs">
              {status === "authenticated" && (
                <div className="flex items-center gap-1.5 text-[#5fa8a0]">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Authenticated</span>
                </div>
              )}
              {status === "invalid_token" && (
                <div className="flex items-center gap-1.5 text-[#c05a4f]">
                  <XCircle className="w-3.5 h-3.5" />
                  <span>Invalid Token</span>
                </div>
              )}
              {status === "sign_in_required" && (
                <div className="flex items-center gap-1.5 text-[#d89a4c]">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Token Required</span>
                </div>
              )}
              {status === "offline" && (
                <div className="flex items-center gap-1.5 text-[#6c7074]">
                  <span className="w-2 h-2 rounded-full bg-[#6c7074]" />
                  <span>Offline</span>
                </div>
              )}
            </div>

            <Button
              variant="outline"
              size="sm"
              type="button"
              onClick={handleTestConnection}
              disabled={testing}
            >
              {testing ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin mr-1.5" />
              ) : null}
              Test Ping
            </Button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="primary" onClick={handleSave}>
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
