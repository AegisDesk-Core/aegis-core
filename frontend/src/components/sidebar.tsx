"use client";

import * as React from "react";
import { Plus, Settings, FileText, CheckCircle, Database, Sparkles, BookOpen } from "lucide-react";
import { ConnectionStatus, KnowledgeDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

interface SidebarProps {
  documents: KnowledgeDocument[];
  connectionStatus: ConnectionStatus;
  demoMode: boolean;
  onNewChat: () => void;
  onOpenSettings: () => void;
}

export function Sidebar({
  documents,
  connectionStatus,
  demoMode,
  onNewChat,
  onOpenSettings,
}: SidebarProps) {
  const isOnline = connectionStatus === "authenticated";

  const getStatusText = () => {
    if (demoMode) return "Demo Mode (Mock)";
    switch (connectionStatus) {
      case "authenticated":
        return "Authenticated";
      case "invalid_token":
        return "Invalid Token";
      case "sign_in_required":
        return "Sign In Required";
      case "checking":
        return "Connecting…";
      case "offline":
      default:
        return "Backend Offline";
    }
  };

  return (
    <aside className="w-72 bg-[#1b1f24] border-r border-[#26292f] flex flex-col h-full select-none flex-none">
      {/* Brand Header */}
      <div className="p-5 border-b border-[#26292f] flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#c68a3d] to-[#9c6a2c] flex items-center justify-center flex-none shadow-md">
          <svg
            className="w-4 h-4 text-[#1b1300]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4 4.5C4 3.67 4.67 3 5.5 3H17L20 6V19.5C20 20.33 19.33 21 18.5 21H5.5C4.67 21 4 20.33 4 19.5V4.5Z" />
            <path d="M8 10H16M8 13.5H16M8 17H12.5" />
          </svg>
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-serif text-lg font-semibold tracking-wide text-[#e9e6e0] leading-none">
            Docent
          </div>
          <div className="text-[11px] text-[#6c7074] mt-1 font-medium">
            Document intelligence
          </div>
        </div>
      </div>

      {/* New Conversation Button */}
      <div className="p-3.5">
        <button
          type="button"
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg bg-[#22262c] hover:bg-[#2a2f37] border border-[#2e3339] hover:border-[#3b414a] text-sm font-medium text-[#e9e6e0] transition-all duration-150 cursor-pointer shadow-sm active:scale-[0.98]"
        >
          <Plus className="w-4 h-4 text-[#c68a3d]" />
          <span>New conversation</span>
        </button>
      </div>

      {/* Knowledge Base Header */}
      <div className="px-4 py-2 flex items-center justify-between text-xs text-[#6c7074] font-medium tracking-wide">
        <div className="flex items-center gap-1.5">
          <Database className="w-3.5 h-3.5" />
          <span>Knowledge base</span>
        </div>
        <span className="font-mono text-[11px] bg-[#15181c] px-1.5 py-0.5 rounded text-[#989b9f]">
          {documents.length}
        </span>
      </div>

      {/* Document List */}
      <div className="flex-1 overflow-y-auto px-3 py-1 space-y-1">
        {documents.length === 0 ? (
          <div className="p-4 text-xs text-[#6c7074] leading-relaxed text-center">
            No indexed documents yet. Documents are synchronized by the connected tenant service.
          </div>
        ) : (
          documents.map((doc) => (
            <div
              key={doc.id}
              className="group flex items-center gap-2.5 p-2 rounded-md hover:bg-[#22262c] transition-colors text-xs cursor-default"
            >
              <FileText className="w-3.5 h-3.5 text-[#5fa8a0] flex-none opacity-80" />
              <div className="flex-1 min-w-0">
                <div className="font-mono text-[#c7cacd] truncate text-[11.5px]" title={doc.filename}>
                  {doc.filename}
                </div>
                {doc.size && (
                  <div className="text-[10px] text-[#6c7074] font-mono mt-0.5">
                    {doc.size}
                  </div>
                )}
              </div>
              <div className="flex-none">
                {doc.status === "ready" && (
                  <span className="inline-flex items-center text-[10px] font-mono text-[#5fa8a0] bg-[#5fa8a0]/10 px-1.5 py-0.5 rounded">
                    ready
                  </span>
                )}
                {doc.status === "indexing" && (
                  <span className="inline-flex items-center text-[10px] font-mono text-[#c68a3d] bg-[#c68a3d]/10 px-1.5 py-0.5 rounded">
                    indexing
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Sidebar Footer: Health Status & Settings Gear */}
      <div className="p-3.5 border-t border-[#26292f] bg-[#181b20] flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={cn(
              "w-2 h-2 rounded-full flex-none transition-all duration-300",
              demoMode
                ? "bg-[#c68a3d] shadow-[0_0_8px_rgba(198,138,61,0.6)]"
                : isOnline
                ? "bg-[#5fa8a0] shadow-[0_0_8px_rgba(95,168,160,0.6)]"
                : connectionStatus === "sign_in_required" || connectionStatus === "invalid_token"
                ? "bg-[#d89a4c]"
                : "bg-[#c05a4f]"
            )}
          />
          <span className="text-xs text-[#989b9f] truncate font-medium">
            {getStatusText()}
          </span>
        </div>

        <button
          type="button"
          onClick={onOpenSettings}
          className="p-1.5 rounded-md text-[#989b9f] hover:text-[#e9e6e0] hover:bg-[#22262c] transition-colors cursor-pointer"
          title="Backend settings"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
