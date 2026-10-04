"use client";

import * as React from "react";
import { FileText, ExternalLink, Copy, Check } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Source } from "@/lib/types";
import { toast } from "sonner";

interface CitationPillProps {
  source: Source;
}

export function CitationPill({ source }: CitationPillProps) {
  const [copied, setCopied] = React.useState(false);
  const filename = source.filename || source.document || "source-document.pdf";
  const pageLabel = source.page ? ` · p.${source.page}` : "";

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    const textToCopy = source.excerpt
      ? `"${source.excerpt}" — [${filename}${pageLabel}]`
      : `${filename}${pageLabel}`;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    toast.success("Citation copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 bg-[#5fa8a0]/15 hover:bg-[#5fa8a0]/25 text-[#5fa8a0] border border-[#5fa8a0]/30 hover:border-[#5fa8a0]/50 px-2.5 py-1 rounded text-[11.5px] font-mono transition-all duration-150 cursor-pointer shadow-sm active:scale-95"
        >
          <FileText className="w-3.5 h-3.5 flex-none opacity-80" />
          <span className="truncate max-w-[200px]">{filename}</span>
          {pageLabel && <span className="text-[#5fa8a0]/70 font-normal">{pageLabel}</span>}
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-80 p-3 bg-[#1c2026] border border-[#2e343d]">
        <div className="flex items-center justify-between pb-2 border-b border-[#2a2f37] mb-2.5">
          <div className="flex items-center gap-1.5 min-w-0">
            <FileText className="w-3.5 h-3.5 text-[#5fa8a0] flex-none" />
            <span className="font-mono text-xs text-[#e9e6e0] font-medium truncate">
              {filename}
            </span>
          </div>
          <button
            onClick={handleCopy}
            className="p-1 text-[#989b9f] hover:text-[#e9e6e0] hover:bg-[#282d35] rounded transition-colors"
            title="Copy citation"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-[#5fa8a0]" /> : <Copy className="w-3.5 h-3.5" />}
          </button>
        </div>

        {source.page && (
          <div className="text-[11px] text-[#989b9f] mb-1.5 flex items-center justify-between font-mono">
            <span>Location: Page {source.page}</span>
            {source.score && (
              <span className="text-[#c68a3d] bg-[#c68a3d]/15 px-1.5 py-0.5 rounded text-[10px]">
                Score: {(source.score * 100).toFixed(0)}%
              </span>
            )}
          </div>
        )}

        <div className="mt-1 bg-[#15181c] p-2.5 rounded border border-[#26292f] text-xs text-[#c9cdd4] italic leading-relaxed">
          {source.excerpt ? (
            `“${source.excerpt}”`
          ) : (
            <span className="text-[#6c7074] not-italic">
              Direct reference citation retrieved from tenant knowledge index.
            </span>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
