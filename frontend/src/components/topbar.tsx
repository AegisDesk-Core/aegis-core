"use client";

import * as React from "react";
import { Trash2, Copy, Check, Menu, BookOpen } from "lucide-react";
import { toast } from "sonner";

interface TopbarProps {
  documentCount: number;
  sessionId: string;
  onClearChat: () => void;
  onToggleSidebar?: () => void;
}

export function Topbar({
  documentCount,
  sessionId,
  onClearChat,
  onToggleSidebar,
}: TopbarProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopySession = () => {
    navigator.clipboard.writeText(sessionId);
    setCopied(true);
    toast.success("Session ID copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <header className="h-14 border-b border-[#26292f] bg-[#15181c]/80 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between flex-none z-10">
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="md:hidden p-1.5 rounded text-[#989b9f] hover:text-[#e9e6e0] hover:bg-[#22262c]"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}

        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-[#c68a3d]" />
          <h2 className="font-serif text-[15px] font-semibold text-[#e9e6e0] tracking-wide">
            Reading room
          </h2>
        </div>

        <span className="hidden sm:inline-block text-xs text-[#6c7074]">
          — server-managed knowledge base ({documentCount} docs)
        </span>
      </div>

      <div className="flex items-center gap-2.5">
        {/* Session ID chip with copy action */}
        <button
          type="button"
          onClick={handleCopySession}
          className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#1e2227] hover:bg-[#262b32] border border-[#2e3339] text-xs font-mono text-[#989b9f] hover:text-[#e9e6e0] transition-colors cursor-pointer"
          title="Click to copy session ID"
        >
          <span>ID: {sessionId}</span>
          {copied ? (
            <Check className="w-3 h-3 text-[#5fa8a0]" />
          ) : (
            <Copy className="w-3 h-3 opacity-60" />
          )}
        </button>

        {/* Clear Conversation button */}
        <button
          type="button"
          onClick={onClearChat}
          className="p-2 rounded-md text-[#989b9f] hover:text-[#c05a4f] hover:bg-[#22262c] transition-colors cursor-pointer"
          title="Clear conversation"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
