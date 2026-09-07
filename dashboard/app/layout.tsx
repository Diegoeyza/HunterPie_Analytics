import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HunterPie Analytics",
  description: "Post-hunt telemetry dashboard for MH Wilds",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{if(localStorage.getItem("hp.theme")==="light")document.documentElement.dataset.theme="light";}catch(e){}})()`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
