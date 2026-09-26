"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useComparacao } from "@/lib/comparacao";

const ITENS: { rotulo: string; href?: string }[] = [
  { rotulo: "Início", href: "/" },
  { rotulo: "Candidatos", href: "/candidatos" },
  { rotulo: "Comparar", href: "/comparar" },
  { rotulo: "Partidos" },
  { rotulo: "Estados" },
  { rotulo: "Patrimônio" },
  { rotulo: "Propostas" },
  { rotulo: "Histórico" },
  { rotulo: "Investigar" },
  { rotulo: "Pergunte aos dados" },
  { rotulo: "Qualidade dos dados" },
  { rotulo: "Fontes" },
];

export function Sidebar() {
  const caminho = usePathname();
  const { lista } = useComparacao();
  return (
    <nav aria-label="Seções" className="flex gap-1 overflow-x-auto border-b border-borda bg-superficie p-2 md:w-56 md:shrink-0 md:flex-col md:overflow-visible md:border-b-0 md:border-r md:p-3">
      <Link href="/" className="mb-3 hidden px-2 text-sm font-semibold leading-tight md:block">
        Laboratório de Análise Eleitoral
        <span className="block text-xs font-normal text-texto-2">Eleições 2026 · dados do TSE</span>
      </Link>
      {ITENS.map((i) => {
        if (!i.href)
          return (
            <span key={i.rotulo} aria-disabled className="flex shrink-0 items-center justify-between gap-2 rounded px-2 py-1.5 text-sm text-texto-3">
              {i.rotulo}
              <span className="rounded bg-superficie-2 px-1 text-[10px]">em breve</span>
            </span>
          );
        const ativo = i.href === "/" ? caminho === "/" : caminho.startsWith(i.href);
        return (
          <Link
            key={i.rotulo}
            href={i.href}
            aria-current={ativo ? "page" : undefined}
            className={`flex shrink-0 items-center justify-between gap-2 rounded px-2 py-1.5 text-sm hover:bg-superficie-2 ${ativo ? "bg-superficie-2 font-semibold" : ""}`}
          >
            {i.rotulo}
            {i.href === "/comparar" && lista.length > 0 && (
              <span className="rounded-full bg-serie px-1.5 text-[11px] font-semibold text-white">{lista.length}</span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
