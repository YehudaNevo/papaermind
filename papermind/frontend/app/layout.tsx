import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PaperMind",
  description: "Query your PDFs with PaperMind",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="bg-gray-100 text-gray-900 min-h-screen flex flex-col">
        <main className="flex-grow container mx-auto px-4 py-8">
          {children}
        </main>
        <footer className="text-center py-4 text-sm text-gray-500">
          Powered by PaperMind
        </footer>
      </body>
    </html>
  );
}
