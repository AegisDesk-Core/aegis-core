"use client";

import * as React from "react";
import { ArrowUp, Paperclip, FileText, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface ComposerProps {
  onSendMessage: (text: string) => void;
  disabled?: boolean;
  backendHost?: string;
  initialValue?: string;
  onClearInitialValue?: () => void;
}

export function Composer({
  onSendMessage,
  disabled = false,
  backendHost = "localhost:8000",
  initialValue = "",
  onClearInitialValue,
}: ComposerProps) {
  const [text, setText] = React.useState(initialValue);
  const [stagedFiles, setStagedFiles] = React.useState<string[]>([]);
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);

  // Sync initialValue if provided externally (e.g. from hint chips)
  React.useEffect(() => {
    if (initialValue) {
      setText(initialValue);
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
        textareaRef.current.focus();
      }
      onClearInitialValue?.();
    }
  }, [initialValue, onClearInitialValue]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setText(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSendMessage(trimmed);
    setText("");
    setStagedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleAttachClick = () => {
    toast.info("Knowledge Base Notice", {
      description: "Documents are managed server-side by the tenant ingestion pipeline.",
    });
  };

  const removeStagedFile = (idx: number) => {
    setStagedFiles((prev) => prev.filter((_, i) => i !== idx));
  };

  const canSend = text.trim().length > 0 && !disabled;

  return (
    <div className="flex-none p-4 pb-6 bg-gradient-to-t from-[#15181c] via-[#15181c]/90 to-transparent">
      <div className="max-w-3xl mx-auto flex flex-col gap-2">
        {/* Staged file chips (if any) */}
        {stagedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-1">
            {stagedFiles.map((file, idx) => (
              <div
                key={idx}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#22262c] border border-[#2e3339] text-xs font-mono text-[#e9e6e0]"
              >
                <FileText className="w-3.5 h-3.5 text-[#5fa8a0]" />
                <span className="truncate max-w-[150px]">{file}</span>
                <button
                  type="button"
                  onClick={() => removeStagedFile(idx)}
                  className="text-[#989b9f] hover:text-[#c05a4f] ml-1"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Input Shell */}
        <div className="relative flex items-end gap-2 bg-[#1e2227] border border-[#2e3339] focus-within:border-[#4a5058] rounded-xl p-2 transition-all duration-200 shadow-md">
          {/* Attach Button */}
          <button
            type="button"
            onClick={handleAttachClick}
            className="flex-none w-8 h-8 rounded-lg bg-[#22262c] text-[#989b9f] hover:text-[#c68a3d] hover:bg-[#282d34] border border-[#2e3339] flex items-center justify-center transition-colors cursor-pointer"
            title="Knowledge base documents are server-managed"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="Ask a question about your documents…"
            className="flex-1 max-h-40 py-1 px-2 bg-transparent text-[#e9e6e0] placeholder-[#6c7074] text-sm focus:outline-none resize-none leading-relaxed"
          />

          {/* Send Button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSend}
            className={cn(
              "flex-none w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150 cursor-pointer shadow-sm",
              canSend
                ? "bg-[#c68a3d] hover:bg-[#d89a4c] text-[#1b1300] active:scale-95"
                : "bg-[#22262c] text-[#6c7074] border border-[#2e3339] cursor-not-allowed opacity-60"
            )}
            title="Send message (Enter)"
          >
            <ArrowUp className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>

        {/* Footer shortcuts & backend hint */}
        <div className="flex items-center justify-between px-2 text-[11px] text-[#6c7074]">
          <span>
            <kbd className="font-mono bg-[#1b1f24] px-1 py-0.5 rounded border border-[#26292f] text-[#8e9297]">
              Enter
            </kbd>{" "}
            to send ·{" "}
            <kbd className="font-mono bg-[#1b1f24] px-1 py-0.5 rounded border border-[#26292f] text-[#8e9297]">
              Shift+Enter
            </kbd>{" "}
            for new line
          </span>
          <span className="font-mono text-[#8a8e94]">
            Backend: {backendHost}
          </span>
        </div>
      </div>
    </div>
  );
}
