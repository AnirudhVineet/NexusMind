"use client";

import { QueryClient, QueryClientProvider, keepPreviousData } from "@tanstack/react-query";
import { SessionProvider } from "next-auth/react";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // 30s default — most lists don't change that often, and this
            // stops every navigation from re-fetching cached data.
            staleTime: 30_000,
            // Keep results in memory for 5 min after last subscriber unmounts
            // so back-navigation paints from cache instantly.
            gcTime: 5 * 60_000,
            // When a query refetches with new params (e.g. filter change),
            // keep showing the prior data instead of flashing to "Loading…".
            placeholderData: keepPreviousData,
            retry: 1,
            refetchOnWindowFocus: false,
            refetchOnReconnect: false,
          },
        },
      })
  );

  return (
    <SessionProvider>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </SessionProvider>
  );
}
