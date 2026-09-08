import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Traffic-RL Dashboard",
  description: "Fixed-timer vs self-learning RL agent, side by side",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
