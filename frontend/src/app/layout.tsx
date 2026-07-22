import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
  title: "Vehicle Health Monitor",
  description:
    "AI-powered predictive maintenance and vehicle health monitoring platform. Track sensors, train ML models, and predict failures in real-time.",
  manifest: "/manifest.json",
  icons: { icon: "/icons/icon-192.svg" },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#0a1628" />
        <meta name="mobile-web-app-capable" content="yes" />
        <script dangerouslySetInnerHTML={{
          __html: `(function(){try{var t=localStorage.getItem("vh-theme")||"system",d=document.documentElement;d.classList.remove("light","dark");var isDark=t==="dark"||(t==="system"&&window.matchMedia("(prefers-color-scheme:dark)").matches);d.classList.add(isDark?"dark":"light")}catch(e){}})()`,
        }} />
        <script dangerouslySetInnerHTML={{
          __html: `if("serviceWorker"in navigator){navigator.serviceWorker.getRegistrations().then(function(r){for(var i of r)i.unregister()})}`,
        }} />
      </head>
      <body className="min-h-screen">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-accent-sky focus:text-white focus:rounded-md focus:outline-none">
          Skip to main content
        </a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
