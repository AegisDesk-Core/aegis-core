"use client";

import * as React from "react";
import { Message } from "@/lib/types";
import { MessageBubble } from "./message-bubble";
import { ChevronDown, Sparkles, BookOpen, ShieldCheck, FileSearch } from "lucide-react";

interface ChatFeedProps {
  messages: Message[];
  isTyping: boolean;
  onSelectHint: (hint: string) => void;
  onRetry?: (text: string) => void;
}

const HINT_QUESTIONS = [
  {
    icon: FileSearch,
    title: "Document Synthesis",
    text: "Summarize the main points across the documents I've uploaded.",
  },
  {
    icon: BookOpen,
    title: "Commercial Analysis",
    text: "What does the source material say about pricing or costs?",
  },
  {
    icon: ShieldCheck,
    title: "Clause Consistency",
    text: "Find any contradictions between the uploaded files.",
  },
];

export function ChatFeed({
  messages,
  isTyping,
  onSelectHint,
  onRetry,
}: ChatFeedProps) {
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const bottomAnchorRef = React.useRef<HTMLDivElement>(null);
  const [showScrollBottom, setShowScrollBottom] = React.useState(false);

  // Auto-scroll on new messages or typing state change
  React.useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // Detect scroll offset for "Scroll to bottom" button
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const isUp = scrollHeight - scrollTop - clientHeight > 150;
    setShowScrollBottom(isUp);
  };

  const scrollToBottom = () => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="relative flex-1 overflow-y-auto px-4 sm:px-8 py-6"
    >
      <div className="max-w-3xl mx-auto flex flex-col gap-6">
        {/* Welcome Empty State */}
        {messages.length === 0 && (
          <div className="my-auto pt-10 pb-6 text-left max-w-xl animate-in fade-in-50 duration-500">
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#c68a3d]/10 border border-[#c68a3d]/25 text-[#c68a3d] text-xs font-medium mb-4">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Multi-Tenant RAG Archive</span>
            </div>

            <h1 className="font-serif text-3xl font-semibold text-[#e9e6e0] tracking-tight mb-3">
              Ask the archive.
            </h1>

            <p className="text-[#989b9f] text-[14.5px] leading-relaxed mb-8">
              Ask questions in plain language. Answers are grounded in the connected
              tenant knowledge base, with verified citations shown beneath each response.
            </p>

            <div className="flex flex-col gap-2.5">
              <span className="text-xs uppercase tracking-wider text-[#6c7074] font-medium">
                Suggested queries
              </span>
              {HINT_QUESTIONS.map((hint, idx) => {
                const Icon = hint.icon;
                return (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => onSelectHint(hint.text)}
                    className="group flex items-start gap-3.5 p-3.5 text-left rounded-lg bg-[#1b1f24] hover:bg-[#22262c] border border-[#26292f] hover:border-[#c68a3d]/50 transition-all duration-200 cursor-pointer active:scale-[0.99]"
                  >
                    <div className="p-2 rounded bg-[#15181c] border border-[#2e3339] text-[#989b9f] group-hover:text-[#c68a3d] group-hover:border-[#c68a3d]/40 transition-colors">
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-[#c7cacd] group-hover:text-[#e9e6e0] mb-0.5">
                        {hint.title}
                      </div>
                      <div className="text-xs text-[#8e9297] group-hover:text-[#b4b7bb] leading-normal line-clamp-2">
                        {hint.text}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Message Thread */}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onRetry={onRetry} />
        ))}

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex items-center gap-3 animate-in fade-in-50 duration-200">
            <div className="w-7 h-7 rounded-md bg-gradient-to-br from-[#c68a3d] to-[#9c6a2c] text-[#1b1300] font-serif font-bold text-sm flex items-center justify-center select-none shadow-md">
              D
            </div>
            <div className="px-4 py-3 rounded-xl rounded-tl-sm bg-[#1b1f24] border border-[#26292f] flex items-center gap-1.5 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-[#989b9f] animate-typing-1" />
              <span className="w-2 h-2 rounded-full bg-[#989b9f] animate-typing-2" />
              <span className="w-2 h-2 rounded-full bg-[#989b9f] animate-typing-3" />
            </div>
          </div>
        )}

        <div ref={bottomAnchorRef} className="h-4" />
      </div>

      {/* Floating Scroll-to-bottom button */}
      {showScrollBottom && (
        <button
          onClick={scrollToBottom}
          className="fixed bottom-24 right-8 p-2 rounded-full bg-[#22262c] text-[#e9e6e0] border border-[#2e3339] shadow-lg hover:bg-[#2c323a] transition-all duration-150 active:scale-95 z-20 cursor-pointer"
          title="Scroll to latest"
        >
          <ChevronDown className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
