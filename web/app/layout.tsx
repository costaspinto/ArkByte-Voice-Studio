import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ArkByte Voice Studio — Creator Workspace",
  description: "A private, local-first AI voice production workspace for creators.",
  applicationName: "ArkByte Voice Studio",
  robots: { index: false, follow: false }
};

export const viewport: Viewport = {
  themeColor: "#080d12",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
