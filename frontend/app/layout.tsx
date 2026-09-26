import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import { Rodape } from "@/components/Rodape";

export const metadata: Metadata = {
  title: "Laboratório de Análise Eleitoral — Eleições 2026",
  description:
    "Explore e compare candidaturas das Eleições 2026 com os dados abertos do TSE. Dados, cálculos e fontes — sem recomendação de voto.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen">
        <div className="flex min-h-screen flex-col md:flex-row">
          <Sidebar />
          <main className="min-w-0 flex-1 px-4 pb-16 pt-4 md:px-8 md:pt-6">{children}</main>
        </div>
        <Rodape />
      </body>
    </html>
  );
}
