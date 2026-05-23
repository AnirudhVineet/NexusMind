import "./globals.css";

import type { Metadata } from "next";

import { ErrorBoundary } from "@/components/error-boundary";
import { Providers } from "@/components/providers";
import { ToastProvider } from "@/components/toast";

export const metadata: Metadata = {
  title: "NexusMind",
  description: "Document intelligence with citation-grounded answers.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ErrorBoundary>
          <Providers>
            <ToastProvider>{children}</ToastProvider>
          </Providers>
        </ErrorBoundary>
      </body>
    </html>
  );
}
