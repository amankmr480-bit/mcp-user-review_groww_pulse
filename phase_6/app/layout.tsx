import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "GROWW Review AI Frontend",
  description: "Phase 6 frontend for notes and email drafts"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

