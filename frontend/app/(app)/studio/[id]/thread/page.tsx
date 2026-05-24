"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useContentItem } from "@/hooks/useContent";
import { patchContent } from "@/services/content";
import { useAutosave } from "@/hooks/useAutosave";

interface Post {
  index?: number;
  text: string;
}

const TWITTER_LIMIT = 280;
const LINKEDIN_LIMIT = 1300;

function platformLimit(platform: string): number {
  return platform === "linkedin" ? LINKEDIN_LIMIT : TWITTER_LIMIT;
}

export default function ThreadEditorPage() {
  const params = useParams();
  const router = useRouter();
  const id = String(params?.id);
  const { item, isLoading } = useContentItem(id);
  const [platform, setPlatform] = useState<"twitter" | "linkedin">("twitter");
  const [posts, setPosts] = useState<Post[]>([]);

  useEffect(() => {
    if (item?.content_json) {
      const c = item.content_json as any;
      const p = Array.isArray(c.posts) ? c.posts : [];
      setPosts(
        p.map((post: any, idx: number) =>
          typeof post === "string"
            ? { index: idx + 1, text: post }
            : { index: post.index ?? idx + 1, text: post.text ?? "" }
        )
      );
    }
  }, [item?.id]);

  const limit = platformLimit(platform);
  const { state, flush } = useAutosave({
    value: { posts },
    save: async (v) => {
      await patchContent(id, v);
    },
  });

  function updatePost(idx: number, text: string) {
    const next = [...posts];
    next[idx] = { ...next[idx], text };
    setPosts(next);
  }

  function splitHere(idx: number) {
    const current = posts[idx];
    if (!current) return;
    const half = Math.floor(current.text.length / 2);
    const sep = current.text.lastIndexOf(" ", half);
    const cut = sep > 0 ? sep : half;
    const first = current.text.slice(0, cut).trim();
    const second = current.text.slice(cut).trim();
    const next = [...posts];
    next.splice(idx, 1, { ...current, text: first }, { text: second });
    setPosts(
      next.map((p, i) => ({ ...p, index: i + 1 }))
    );
  }

  function addPost() {
    setPosts([...posts, { index: posts.length + 1, text: "" }]);
  }

  function removePost(idx: number) {
    setPosts(posts.filter((_, i) => i !== idx).map((p, i) => ({ ...p, index: i + 1 })));
  }

  if (isLoading) return <p className="text-muted-foreground text-sm">Loading…</p>;
  if (!item || item.content_type !== "thread") {
    return <p className="text-muted-foreground text-sm">Not a thread row.</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => router.back()} className="text-primary hover:underline text-sm">
          ← Back
        </button>
        <h1 className="text-xl font-semibold flex-1">Thread Editor</h1>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value as any)}
          className="bg-background border border-border rounded px-2 py-1 text-sm"
        >
          <option value="twitter">Twitter / X</option>
          <option value="linkedin">LinkedIn</option>
        </select>
        <span className="text-xs text-muted-foreground">{state === "saving" ? "Saving…" : state === "saved" ? "Saved" : ""}</span>
      </div>

      <div className="space-y-2">
        {posts.map((p, i) => {
          const overLimit = p.text.length > limit;
          return (
            <div
              key={i}
              className={`bg-surface border rounded-lg p-3 space-y-1 ${overLimit ? "border-red-500" : "border-border"}`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-primary font-medium">Post {p.index ?? i + 1}</span>
                <div className="flex gap-2">
                  {overLimit && (
                    <button onClick={() => splitHere(i)} className="text-xs text-amber-400 hover:underline">
                      Split here
                    </button>
                  )}
                  <button onClick={() => removePost(i)} className="text-xs text-red-400 hover:underline">
                    Remove
                  </button>
                </div>
              </div>
              <textarea
                className="w-full bg-background border border-border rounded px-2 py-1.5 text-sm"
                rows={3}
                value={p.text}
                onChange={(e) => updatePost(i, e.target.value)}
              />
              <p className={`text-xs ${overLimit ? "text-red-400" : "text-muted-foreground"}`}>
                {p.text.length} / {limit}
              </p>
            </div>
          );
        })}
        <button
          onClick={addPost}
          className="text-xs px-3 py-1 rounded border border-border hover:bg-accent/10"
        >
          + Add post
        </button>
      </div>

      <div className="flex justify-end gap-2 sticky bottom-2 bg-background py-2">
        <button onClick={() => flush()} className="px-3 py-1.5 text-sm border border-border rounded">
          Save now
        </button>
      </div>
    </div>
  );
}
