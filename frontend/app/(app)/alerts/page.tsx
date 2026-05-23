"use client";
import { useState } from "react";
import { useAlertRules } from "@/hooks/useAlerts";
import type { AlertCreate } from "@/services/alerts";

const ALERT_TYPES = [
  { value: "interest_match", label: "Interest Match", desc: "Alert when new docs match your interests" },
  { value: "contradiction", label: "Contradiction", desc: "Alert when contradictions are detected" },
  { value: "topic_keyword", label: "Topic Keyword", desc: "Alert on keyword matches in new content" },
  { value: "entity_mention", label: "Entity Mention", desc: "Alert when watched entities appear" },
] as const;

type Tab = "alerts" | "builder" | "settings";

export default function AlertsPage() {
  const [tab, setTab] = useState<Tab>("alerts");
  const { rules, isLoading, create, update, remove } = useAlertRules();

  const [newRule, setNewRule] = useState<AlertCreate>({ name: "", alert_type: "topic_keyword", config: { keywords: [] } });
  const [keywords, setKeywords] = useState("");

  const tabs: { key: Tab; label: string }[] = [
    { key: "alerts", label: "My Alerts" },
    { key: "builder", label: "Rule Builder" },
    { key: "settings", label: "Settings" },
  ];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Alerts</h1>
        <p className="text-muted text-sm mt-1">Configure semantic alerts and manage notification preferences.</p>
      </header>

      <div className="flex gap-1 border-b border-border">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${tab === t.key ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"}`}
          >{t.label}</button>
        ))}
      </div>

      {/* My Alerts tab */}
      {tab === "alerts" && (
        <div className="space-y-4">
          {isLoading ? <p className="text-muted text-sm">Loading…</p> : rules.length === 0 ? (
            <div className="bg-surface border border-border rounded-lg p-12 text-center">
              <p className="text-muted text-sm">No alert rules configured.</p>
              <button onClick={() => setTab("builder")} className="text-accent text-sm mt-2 hover:underline">Create your first rule →</button>
            </div>
          ) : (
            <div className="space-y-2">
              {rules.map((rule) => {
                const typeInfo = ALERT_TYPES.find((t) => t.value === rule.alert_type);
                return (
                  <div key={rule.id} className="bg-surface border border-border rounded-lg p-4 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">{rule.name}</p>
                      <p className="text-xs text-muted mt-0.5">{typeInfo?.label ?? rule.alert_type} — {typeInfo?.desc}</p>
                      {rule.config?.keywords && (
                        <div className="flex gap-1 mt-1.5 flex-wrap">
                          {(rule.config.keywords as string[]).map((kw) => (
                            <span key={kw} className="text-xs bg-border/30 rounded px-1.5 py-0.5">{kw}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <button onClick={() => update(rule.id, { enabled: !rule.enabled })}
                        className={`text-xs px-3 py-1 rounded-full border ${rule.enabled ? "border-green-500/30 text-green-400 bg-green-500/10" : "border-border text-muted"}`}
                      >{rule.enabled ? "Active" : "Paused"}</button>
                      <button onClick={() => { if (confirm("Delete this rule?")) remove(rule.id); }}
                        className="text-xs text-red-400 hover:text-red-300">Delete</button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Rule Builder tab */}
      {tab === "builder" && (
        <div className="bg-surface border border-border rounded-lg p-6 space-y-4 max-w-lg">
          <h2 className="text-lg font-medium">Create Alert Rule</h2>

          <div className="space-y-3">
            <input placeholder="Rule name" value={newRule.name}
              onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm" />

            <select value={newRule.alert_type}
              onChange={(e) => setNewRule({ ...newRule, alert_type: e.target.value, config: {} })}
              className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm">
              {ALERT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>

            {newRule.alert_type === "topic_keyword" && (
              <div>
                <label className="text-xs text-muted block mb-1">Keywords (comma-separated)</label>
                <input placeholder="ai, machine learning, neural" value={keywords}
                  onChange={(e) => setKeywords(e.target.value)}
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm" />
              </div>
            )}

            {newRule.alert_type === "interest_match" && (
              <div>
                <label className="text-xs text-muted block mb-1">Similarity Threshold</label>
                <input type="number" step="0.05" min="0" max="1" defaultValue="0.65"
                  onChange={(e) => setNewRule({ ...newRule, config: { threshold: parseFloat(e.target.value) } })}
                  className="w-full px-3 py-2 rounded-md bg-background border border-border text-sm" />
              </div>
            )}
          </div>

          <button
            onClick={async () => {
              if (!newRule.name) return;
              const config = newRule.alert_type === "topic_keyword"
                ? { keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean) }
                : newRule.config;
              await create({ ...newRule, config });
              setNewRule({ name: "", alert_type: "topic_keyword", config: {} });
              setKeywords("");
              setTab("alerts");
            }}
            className="px-4 py-2 rounded-md bg-accent text-white text-sm hover:bg-accent/80"
          >Create Rule</button>
        </div>
      )}

      {/* Settings tab */}
      {tab === "settings" && (
        <div className="bg-surface border border-border rounded-lg p-6 space-y-6 max-w-lg">
          <h2 className="text-lg font-medium">Notification Settings</h2>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Browser Push Notifications</p>
                <p className="text-xs text-muted">Receive push notifications in your browser</p>
              </div>
              <button className="text-xs px-3 py-1 rounded border border-border text-muted hover:text-foreground">
                Enable
              </button>
            </div>

            <div className="border-t border-border pt-4">
              <p className="text-sm font-medium">Email Digest</p>
              <p className="text-xs text-muted mb-3">Receive a daily email summary of unread notifications</p>
              <div className="flex items-center gap-3">
                <label className="text-xs text-muted">Send at:</label>
                <select className="px-3 py-1.5 rounded-md bg-background border border-border text-sm" defaultValue="8">
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={i}>{i.toString().padStart(2, "0")}:00</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="border-t border-border pt-4">
              <button className="text-xs px-3 py-1.5 rounded border border-accent text-accent hover:bg-accent/10">
                Send Test Push Notification
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
