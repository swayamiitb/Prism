import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Context Brain — How the company works, as executable skills",
  description:
    "An AI that understands how a company works end-to-end and turns it into executable skills. Local models, living knowledge graph.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
