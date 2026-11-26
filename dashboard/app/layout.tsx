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
        {/* Runs before first paint: sets the theme without a flash and gets
            <html lang> right for assistive tech. The prerendered text is still
            English — the client switches locale on mount (static export, so
            the server cannot know the preference). */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{
if(localStorage.getItem("hp.theme")==="light")document.documentElement.dataset.theme="light";
var l=new URLSearchParams(location.search).get("lang")||localStorage.getItem("hp.locale");
if(l!=="en"&&l!=="ja")l=(navigator.language||"").toLowerCase().indexOf("ja")===0?"ja":"en";
if(l==="ja")document.documentElement.lang="ja";
}catch(e){}})()`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
