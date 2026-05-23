"use client";
import { useCallback, useEffect, useState } from "react";
import { listNotifications, markRead, markAllRead, dismissNotification, Notification } from "@/services/alerts";

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { items, unread_count } = await listNotifications({ limit: 50 });
      setNotifications(items);
      setUnreadCount(unread_count);
    } catch {} finally { setIsLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 30000); // poll every 30s
    return () => clearInterval(interval);
  }, [load]);

  const read = useCallback(async (id: string) => {
    await markRead(id);
    setNotifications(p => p.map(n => n.id === id ? { ...n, read_at: new Date().toISOString() } : n));
    setUnreadCount(p => Math.max(0, p - 1));
  }, []);

  const readAll = useCallback(async () => {
    await markAllRead();
    const now = new Date().toISOString();
    setNotifications(p => p.map(n => ({ ...n, read_at: n.read_at ?? now })));
    setUnreadCount(0);
  }, []);

  const dismiss = useCallback(async (id: string) => {
    await dismissNotification(id);
    setNotifications(p => p.filter(n => n.id !== id));
    setUnreadCount(p => Math.max(0, p - 1));
  }, []);

  return { notifications, unreadCount, isLoading, read, readAll, dismiss };
}
