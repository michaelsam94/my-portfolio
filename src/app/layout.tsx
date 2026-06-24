import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import SkipLink from "@/components/SkipLink";
import ThemeProvider from "@/components/ThemeProvider";
import ThemeToggle from "@/components/ThemeToggle";
import { defaultMetadata, structuredData } from "@/lib/metadata";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "600", "700", "800"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = defaultMetadata;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <ThemeProvider>
          <div className="site-shell">
            <SkipLink />
            <header className="site-header">
              <div className="header-inner">
                <Link className="brand-mark" href="/" aria-label="Michael Sam home">
                  Michael Sam
                </Link>
                <div className="header-actions">
                  <a className="header-link" href="#projects">
                    Work
                  </a>
                  <a className="header-link" href="#apps">
                    Apps
                  </a>
                  <a className="header-link" href="#vscode">
                    Extensions
                  </a>
                  <a className="header-link" href="#contact">
                    Contact
                  </a>
                  <ThemeToggle />
                </div>
              </div>
            </header>
            {children}
          </div>
          <script type="application/ld+json">{JSON.stringify(structuredData())}</script>
        </ThemeProvider>
      </body>
    </html>
  );
}
