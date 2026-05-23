"use client";
import { useState } from "react";
import { useWorkflows, useFeeds, useEmailSettings } from "@/hooks/useWorkflows";
import type { WorkflowCreate, FeedCreate } from "@/services/workflows";

const TRIGGER_EVENTS = [
  { value: "document_ingested", label: "Document Ingested" },
  { value: "contradiction_detected", label: "Contradiction Detected" },
  { value: "semantic_alert_matched", label: "Semantic Alert Matched" },
  { value: "card_due_threshold", label: "Cards Due Threshold" },
  { value: "brief_generated", label: "Research Brief Generated" },
  { value: "gap_detected", label: "Knowledge Gap Detected" },
];

const ACTION_TYPES = [
  { value: "send_email", label: "Send Email" },
  { value: "fire_webhook", label: "Fire Webhook" },
  { value: "mark_tag", label: "Add Tag" },
  { value: "create_research_brief", label: "Create Research Brief" },
  { value: "generate_cards", label: "Generate Flashcards" },
  { value: "push_notification", label: "Push Notification" },
];

type Tab = "rules" | "feeds" | "history";

export default function WorkflowsPage() {
  const [tab, setTab] = useState<Tab>("rules");
  const [showCreate, setShowCreate] = useState(false);
  const [showFeedCreate, setShowFeedCreate] = useState(false);

  const { workflows, isLoading: wfLoading, create: createWf, update: updateWf, remove: removeWf } = useWorkflows();
  const { feeds, isLoading: feedLoading, create: createFeed, update: updateFeed, remove: removeFeed, pollNow } = useFeeds();
  const { settings: emailSettings, saving: emailSaving, save: saveEmail } = useEmailSettings();

  const [newWf, setNewWf] = useState<WorkflowCreate>({ name: "", trigger_event: "document_ingested", action_type: "send_email" });
  const [newFeed, setNewFeed] = useState<FeedCreate>({ url: "", title: "", interval_minutes: 360 });

  const tabs: { key: Tab; label: string }[] = [
    { key: "rules", label: "Rules" },
    { key: "feeds", label: "RSS Feeds" },
    { key: "history", label: "Run History" },
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Workflows</h1>
        <p className="text-muted text-sm mt-1">Automate actions based on events in your knowledge graph.</p>
      </header>

      <div className="flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"}`}
          >{t.label}</button>
        ))}
      </div>

      {/* Rules tab */}
      {tab === "rules" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setShowCreate(!showCreate)}
              className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80"
            >{showCreate ? "Cancel" : "New Rule"}</button>
          </div>

          {showCreate && (
            <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
              <input placeholder="Rule name" value={newWf.name} onChange={(e) => setNewWf({ ...newWf, name: e.target.value })}
                className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm" />
              <div className="grid grid-cols-2 gap-3">
                <select value={newWf.trigger_event} onChange={(e) => setNewWf({ ...newWf, trigger_event: e.target.value })}
                  className="px-3 py-2 rounded-md bg-background border border-border text-sm">
                  {TRIGGER_EVENTS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
                <select value={newWf.action_type} onChange={(e) => setNewWf({ ...newWf, action_type: e.target.value })}
                  className="px-3 py-2 rounded-md bg-background border border-border text-sm">
                  {ACTION_TYPES.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
                </select>
              </div>
              <button onClick={async () => { if (newWf.name) { await createWf(newWf); setShowCreate(false); setNewWf({ name: "", trigger_event: "document_ingested", action_type: "send_email" }); }}}
                className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80">Create</button>
            </div>
          )}

          {wfLoading ? <p className="text-muted text-sm">Loading…</p> : workflows.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg p-12 text-center text-muted text-sm">
              No workflows yet. Create a rule to automate actions.
            </div>
          ) : (
            <div className="space-y-2">
              {workflows.map((wf) => (
                <div key={wf.id} className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{wf.name}</p>
                    <p className="text-xs text-muted mt-0.5">
                      {TRIGGER_EVENTS.find((t) => t.value === wf.trigger_event)?.label} → {ACTION_TYPES.find((a) => a.value === wf.action_type)?.label}
                    </p>
                    <p className="text-xs text-muted">{wf.run_count} runs{wf.last_run_at ? ` • Last: ${new Date(wf.last_run_at).toLocaleDateString()}` : ""}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={() => updateWf(wf.id, { enabled: !wf.enabled })}
                      className={`text-xs px-3 py-1 rounded-full border ${wf.enabled ? "border-green-500/30 text-green-400 bg-green-500/10" : "border-border text-muted"}`}
                    >{wf.enabled ? "Enabled" : "Disabled"}</button>
                    <button onClick={() => { if (confirm("Delete workflow?")) removeWf(wf.id); }}
                      className="text-xs text-red-400 hover:text-red-300">Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Feeds tab */}
      {tab === "feeds" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setShowFeedCreate(!showFeedCreate)}
              className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80"
            >{showFeedCreate ? "Cancel" : "Add Feed"}</button>
          </div>

          {showFeedCreate && (
            <div className="bg-surface border border-border rounded-lg p-4 space-y-3">
              <input placeholder="Feed URL" value={newFeed.url} onChange={(e) => setNewFeed({ ...newFeed, url: e.target.value })}
                className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm" />
              <input placeholder="Feed title" value={newFeed.title} onChange={(e) => setNewFeed({ ...newFeed, title: e.target.value })}
                className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm" />
              <button onClick={async () => { if (newFeed.url && newFeed.title) { await createFeed(newFeed); setShowFeedCreate(false); setNewFeed({ url: "", title: "", interval_minutes: 360 }); }}}
                className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80">Add</button>
            </div>
          )}

          {feedLoading ? <p className="text-muted text-sm">Loading…</p> : feeds.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg p-12 text-center text-muted text-sm">
              No RSS feeds configured. Add a feed to auto-ingest articles.
            </div>
          ) : (
            <div className="space-y-2">
              {feeds.map((feed) => (
                <div key={feed.id} className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{feed.title}</p>
                    <p className="text-xs text-muted truncate max-w-md">{feed.url}</p>
                    <p className="text-xs text-muted">Every {feed.interval_minutes}min{feed.last_fetched_at ? ` • Last: ${new Date(feed.last_fetched_at).toLocaleString()}` : ""}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button onClick={() => pollNow(feed.id)} className="text-xs px-3 py-1 rounded border border-border text-muted hover:text-foreground">Poll Now</button>
                    <button onClick={() => updateFeed(feed.id, { enabled: !feed.enabled })}
                      className={`text-xs px-3 py-1 rounded-full border ${feed.enabled ? "border-green-500/30 text-green-400 bg-green-500/10" : "border-border text-muted"}`}
                    >{feed.enabled ? "On" : "Off"}</button>
                    <button onClick={() => { if (confirm("Delete feed?")) removeFeed(feed.id); }}
                      className="text-xs text-red-400 hover:text-red-300">Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* History tab */}
      {tab === "history" && (
        <div className="bg-surface border border-border rounded-lg p-6 text-center text-muted text-sm">
          <p className="py-12">Workflow run history will appear here when workflows execute.</p>
        </div>
      )}
    </div>
  );
}
