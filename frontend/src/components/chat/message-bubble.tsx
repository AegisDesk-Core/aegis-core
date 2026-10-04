"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import { Copy, Check, AlertCircle, Sparkles } from "lucide-react";
import { Message } from "@/lib/types";
import { CitationPill } from "./citation-pill";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface MessageBubbleProps {
  message: Message;
  onRetry?: (text: string) => void;
}

export function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const [copied, setCopied] = React.useState(false);
  const isUser = message.role === "user";

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    toast.success("Message copied");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className={cn(
        "group flex gap-3 items-start w-full transition-opacity duration-200",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      {isUser ? (
        <div className="flex-none w-7 h-7 rounded-md bg-[#22262c] border border-[#2e3339] text-[#989b9f] flex items-center justify-center text-xs font-medium mt-0.5 select-none shadow-sm">
          You
        </div>
      ) : (
        <div className="flex-none w-7 h-7 rounded-md bg-gradient-to-br from-[#c68a3d] to-[#9c6a2c] text-[#1b1300] font-serif font-bold text-sm flex items-center justify-center mt-0.5 select-none shadow-md">
          D
        </div>
      )}

      {/* Bubble Container */}
      <div
        className={cn(
          "max-w-[80%] min-w-0 flex flex-col",
          isUser ? "items-end" : "items-start"
        )}
      >
        <div
          className={cn(
            "relative px-4 py-3 rounded-xl text-[14px] leading-relaxed shadow-sm break-words transition-all duration-150",
            isUser
              ? "bg-[#c68a3d]/18 border border-[#c68a3d]/40 text-[#f6e5cd] rounded-tr-sm"
              : message.isError
              ? "bg-[#c05a4f]/15 border border-[#c05a4f]/35 text-[#f0958b] rounded-tl-sm"
              : "bg-[#1b1f24] border border-[#26292f] text-[#e9e6e0] rounded-tl-sm"
          )}
        >
          {message.isError && (
            <div className="flex items-center gap-2 mb-2 text-[#e67568] font-medium text-xs">
              <AlertCircle className="w-4 h-4 flex-none" />
              <span>Connection Notice</span>
            </div>
          )}

          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : (
            <div className="markdown-content prose prose-invert max-w-none text-sm leading-relaxed">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}

          {/* Quick copy message button */}
          <button
            onClick={handleCopy}
            className="absolute top-2.5 right-2 opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-[#282d35] text-[#989b9f] hover:text-[#e9e6e0] transition-opacity"
            title="Copy message"
          >
            {copied ? (
              <Check className="w-3 h-3 text-[#5fa8a0]" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </button>
        </div>

        {/* Retry Button if error */}
        {message.isError && onRetry && (
          <button
            onClick={() => onRetry(message.content)}
            className="mt-1.5 text-xs text-[#c68a3d] hover:underline cursor-pointer flex items-center gap-1 self-start"
          >
            Retry request
          </button>
        )}

        {/* Sources Section */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-2.5 flex flex-col gap-1.5 w-full">
            <div className="text-[11px] text-[#6c7074] font-medium flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[#5fa8a0]" />
              <span>Verified Sources ({message.sources.length})</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {message.sources.map((source, idx) => (
                <CitationPill key={idx} source={source} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
