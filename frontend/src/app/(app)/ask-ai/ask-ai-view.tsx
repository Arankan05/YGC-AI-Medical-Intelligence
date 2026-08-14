"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import {
  ArrowRight,
  Check,
  FileText,
  Info,
  MapPin,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { api, toErrorMessage } from "@/lib/api";
import {
  answerPipeline,
  askAiScopeNote,
  askAiSuggestions,
  safetyRules,
} from "@/lib/data";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/lib/types";

/**
 * Figma: 12 · Ask AI (node 30:846) and
 * 13 · Ask AI — No-Diagnosis Safety (node 32:934), which share this layout.
 */
export function AskAiView({
  thread,
  variant,
}: {
  thread: ChatMessage[];
  variant: "default" | "safety";
}) {
  const [messages, setMessages] = useState(thread);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const value = question.trim();
    if (!value) return;

    setSending(true);
    setError(null);
    try {
      const answer = await api().askAi({ question: value });
      setMessages((current) => [
        ...current,
        {
          id: `local-${current.length}`,
          role: "user",
          paragraphs: [value],
        },
        answer,
      ]);
      setQuestion("");
    } catch (caught) {
      setError(toErrorMessage(caught));
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex min-h-full w-full flex-col gap-4 px-4 py-[22px] md:px-[26px] xl:flex-row xl:items-stretch">
      {/* panel · chat (30:940) */}
      <section className="flex w-full min-w-0 flex-1 flex-col rounded-xl border border-neutral-200 bg-neutral-0 shadow-card">
        <div className="flex items-center justify-between gap-3 px-[18px] py-3">
          <div className="flex items-center gap-2.5">
            <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-brand-700">
              <Sparkles className="size-4 text-neutral-0" strokeWidth={1.8} />
            </span>
            <span className="flex flex-col gap-px">
              <span className="text-sm leading-5 font-medium text-neutral-900">
                Record assistant
              </span>
              <span className="text-xs leading-4 font-medium text-neutral-500">
                Searching your uploaded medical records
              </span>
            </span>
          </div>
          <button
            type="button"
            onClick={() => setMessages([])}
            className="cursor-pointer text-[13px] leading-[18px] font-medium text-neutral-500 transition-colors hover:text-neutral-700"
          >
            Clear conversation
          </button>
        </div>
        <div className="h-px w-full bg-neutral-200" />

        {/* thread (30:951) */}
        <div className="scrollbar-thin flex max-h-[62vh] min-h-[320px] flex-1 flex-col gap-4 overflow-y-auto p-[18px]">
          {messages.length === 0 && (
            <p className="py-16 text-center text-sm leading-[21px] text-neutral-500">
              Ask a question about your uploaded records to start a conversation.
            </p>
          )}
          {messages.map((message) =>
            message.role === "user" ? (
              <div key={message.id} className="flex w-full justify-end">
                <div className="max-w-[430px] rounded-xl bg-sidebar-active-bg px-4 py-[11px] text-sm leading-[21px] text-sidebar-active-ink">
                  {message.paragraphs.join("\n")}
                </div>
              </div>
            ) : (
              <div key={message.id} className="flex w-full items-start gap-[11px]">
                <span className="flex size-[30px] shrink-0 items-center justify-center rounded-md bg-brand-50">
                  <Sparkles
                    className="size-[15px] text-brand-700"
                    strokeWidth={1.8}
                  />
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-[11px] rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-[13px]">
                  {message.refusal && (
                    <div className="flex w-full items-center gap-[11px] rounded-[10px] border border-risk-med-border bg-risk-med-bg px-3.5 py-3">
                      <TriangleAlert
                        className="size-[18px] shrink-0 text-risk-med"
                        strokeWidth={1.8}
                      />
                      <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                        <span className="type-overline text-risk-med">
                          {message.refusal.overline}
                        </span>
                        <span className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
                          {message.refusal.headline}
                        </span>
                      </span>
                    </div>
                  )}

                  {message.paragraphs.map((paragraph) => (
                    <p
                      key={paragraph.slice(0, 40)}
                      className="text-sm leading-[21px] text-neutral-800"
                    >
                      {paragraph}
                    </p>
                  ))}

                  {message.refusal && (
                    <div className="flex w-full flex-col gap-2 rounded-[9px] border border-neutral-200 bg-neutral-0 px-[13px] py-[11px]">
                      <p className="type-overline text-neutral-500">
                        TRY ASKING INSTEAD
                      </p>
                      {message.refusal.suggestions.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => setQuestion(suggestion)}
                          className="flex w-full cursor-pointer items-center gap-[9px] text-left"
                        >
                          <ArrowRight
                            className="size-[13px] shrink-0 text-brand-800"
                            strokeWidth={1.8}
                          />
                          <span className="text-[13px] leading-[19px] text-brand-800 hover:underline">
                            {suggestion}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}

                  {message.citations && message.citations.length > 0 && (
                    <div className="flex w-full flex-col gap-[7px] rounded-[9px] border border-neutral-200 bg-neutral-0 px-[13px] py-[11px]">
                      <p className="type-overline text-neutral-500">EVIDENCE</p>
                      {message.citations.map((citation) => (
                        <div
                          key={`${citation.documentTitle}-${citation.page}`}
                          className="flex w-full flex-wrap items-center gap-[9px]"
                        >
                          <FileText
                            className="size-[13px] shrink-0 text-brand-700"
                            strokeWidth={1.8}
                          />
                          <Link
                            href="/documents"
                            className="text-xs leading-4 font-semibold text-brand-700 hover:underline"
                          >
                            {citation.documentTitle} · p{citation.page}
                          </Link>
                          <p className="min-w-0 flex-1 text-[13px] leading-[19px] text-neutral-600">
                            {citation.quote}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  {typeof message.confidence === "number" && (
                    <div className="flex w-full flex-wrap items-center gap-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs leading-4 font-medium text-neutral-500">
                          Confidence
                        </span>
                        <span className="h-1.5 w-[90px] overflow-hidden rounded-full bg-neutral-200">
                          <span
                            className="block h-1.5 rounded-full bg-brand-600"
                            style={{ width: `${message.confidence}%` }}
                          />
                        </span>
                        <span className="text-xs leading-4 font-semibold text-neutral-700">
                          {message.confidence}%
                        </span>
                      </div>
                      <span className="h-[13px] w-px bg-neutral-300" />
                      <span className="min-w-0 flex-1 text-xs leading-4 font-medium text-neutral-600">
                        {message.guidance}
                      </span>
                    </div>
                  )}

                  {message.cta && (
                    <div className="flex w-full flex-wrap items-center gap-2.5">
                      <Button
                        render={<Link href="/providers" />}
                        size="sm"
                        className="gap-[9px] px-3.5 py-2.5"
                      >
                        <MapPin className="size-3.5" strokeWidth={1.8} />
                        {message.cta.label}
                      </Button>
                      <span className="text-xs leading-4 font-medium text-neutral-500">
                        {message.cta.note}
                      </span>
                    </div>
                  )}

                  {message.refusal && (
                    <div className="flex w-full items-center gap-[9px]">
                      <Info
                        className="size-3.5 shrink-0 text-neutral-500"
                        strokeWidth={1.8}
                      />
                      <p className="text-xs leading-4 font-medium text-neutral-600">
                        {message.refusal.footnote}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )
          )}
        </div>

        <div className="h-px w-full bg-neutral-200" />

        {/* composer (30:1015) */}
        <form
          onSubmit={handleSubmit}
          className="flex w-full flex-col gap-[11px] px-[18px] pt-3.5 pb-4"
        >
          <div className="flex flex-wrap gap-2">
            {askAiSuggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => setQuestion(suggestion)}
                className="cursor-pointer rounded-full border border-neutral-200 bg-neutral-0 px-3 py-[7px] text-xs leading-4 font-medium text-neutral-600 transition-colors hover:bg-neutral-50"
              >
                {suggestion}
              </button>
            ))}
          </div>
          <div className="flex w-full items-center gap-2.5 rounded-[10px] border border-neutral-300 bg-neutral-0 py-2 pr-2 pl-[15px] focus-within:border-brand-700">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about your medical records…"
              aria-label="Ask about your medical records"
              className="min-w-0 flex-1 bg-transparent text-sm leading-[21px] text-neutral-900 outline-none placeholder:text-neutral-600"
            />
            <Button type="submit" size="sm" disabled={sending} className="gap-2 px-3.5 py-[9px]">
              {sending ? "Asking…" : "Ask"}
              <ArrowRight className="size-3.5" strokeWidth={1.8} />
            </Button>
          </div>
          {error && (
            <p
              role="alert"
              className="rounded-[10px] border border-risk-high-border bg-risk-high-bg px-3.5 py-2.5 text-[13px] leading-[19px] text-risk-high"
            >
              {error}
            </p>
          )}
        </form>
      </section>

      {/* side-column (30:1031) */}
      <aside className="flex w-full flex-col gap-3.5 xl:w-[320px] xl:shrink-0">
        <div className="flex w-full flex-col gap-3 rounded-xl border border-neutral-200 bg-neutral-0 px-4 py-[15px] shadow-card">
          <h2 className="text-base leading-6 font-semibold tracking-[-0.1px] text-neutral-900">
            {variant === "safety" ? "Enforced safety rules" : "How an answer is built"}
          </h2>
          {(variant === "safety" ? safetyRules : answerPipeline).map(
            (item, index) => (
              <div key={item.title} className="flex w-full items-start gap-[11px]">
                <span
                  className={cn(
                    "flex size-[22px] shrink-0 items-center justify-center rounded-full text-xs leading-4 font-semibold",
                    variant === "safety"
                      ? "bg-status-ok-bg text-status-ok"
                      : "bg-brand-50 text-brand-800"
                  )}
                >
                  {variant === "safety" ? (
                    <Check className="size-3" strokeWidth={2.4} />
                  ) : (
                    index + 1
                  )}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-[13px] leading-[18px] font-medium text-neutral-800">
                    {item.title}
                  </span>
                  <span className="text-xs leading-4 font-medium text-neutral-500">
                    {item.description}
                  </span>
                </span>
              </div>
            )
          )}
        </div>

        <div className="flex w-full flex-1 flex-col gap-2 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3.5">
          <div className="flex items-center gap-[9px]">
            <ShieldCheck
              className="size-4 shrink-0 text-brand-800"
              strokeWidth={1.8}
            />
            <p className="type-overline text-brand-800">SCOPE AND LIMITS</p>
          </div>
          <p className="text-[13px] leading-[19px] text-neutral-700">
            {askAiScopeNote}
          </p>
          <Link
            href={variant === "safety" ? "/ask-ai" : "/ask-ai/safety"}
            className="mt-auto pt-2 text-[13px] leading-[18px] font-medium text-brand-700 hover:underline"
          >
            {variant === "safety"
              ? "Back to the conversation"
              : "See how a diagnosis request is handled"}
          </Link>
        </div>
      </aside>
    </div>
  );
}
