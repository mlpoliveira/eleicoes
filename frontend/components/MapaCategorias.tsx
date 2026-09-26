"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { numero } from "@/lib/formato";

interface Mapa {
  descricao: string;
  mapa: { categoria: string; tipo: string; observacao: string | null; qt_bens: number }[];
  tipos_fora_do_mapa: { tipo: string; qt_bens: number }[];
}

// Link "ver mapa de categorias": a categoria de bem é um CÁLCULO documentado (T4).
export function MapaCategorias() {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [mapa, setMapa] = useState<Mapa | null>(null);
  const abrir = () => {
    dialogo.current?.showModal();
    if (!mapa) api<Mapa>("/categorias-bens").then(setMapa).catch(() => undefined);
  };
  return (
    <>
      <button type="button" onClick={abrir} className="text-[11px] text-destaque underline decoration-dotted underline-offset-2">
        ver mapa de categorias
      </button>
      <dialog ref={dialogo} className="m-auto w-[min(94vw,760px)] rounded-lg border border-borda bg-superficie p-0 text-texto backdrop:bg-black/40">
        <div className="p-5 text-sm">
          <h2 className="mb-2 text-base font-semibold">Mapa de categorias de bens</h2>
          {!mapa ? <p className="text-texto-2">Carregando…</p> : (
            <>
              <p className="mb-3 text-texto-2">{mapa.descricao}</p>
              <div className="max-h-[60vh] overflow-auto rounded border border-borda">
                <table className="w-full text-xs">
                  <thead className="sticky top-0 bg-superficie-2 text-left text-texto-2">
                    <tr><th className="px-2 py-1">Categoria</th><th className="px-2 py-1">Tipo de bem (TSE)</th><th className="px-2 py-1 text-right">Bens</th><th className="px-2 py-1">Observação</th></tr>
                  </thead>
                  <tbody>
                    {mapa.mapa.map((m) => (
                      <tr key={m.tipo} className="border-t border-borda">
                        <td className="px-2 py-1">{m.categoria}</td><td className="px-2 py-1">{m.tipo}</td>
                        <td className="px-2 py-1 text-right tabular-nums">{numero(m.qt_bens)}</td>
                        <td className="px-2 py-1 text-texto-2">{m.observacao ?? ""}</td>
                      </tr>
                    ))}
                    {mapa.tipos_fora_do_mapa.map((m) => (
                      <tr key={m.tipo} className="border-t border-borda">
                        <td className="px-2 py-1 ausente">sem categoria no mapa</td><td className="px-2 py-1">{m.tipo}</td>
                        <td className="px-2 py-1 text-right tabular-nums">{numero(m.qt_bens)}</td><td />
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          <form method="dialog" className="mt-4 text-right">
            <button className="rounded border border-borda px-3 py-1 hover:bg-superficie-2">Fechar</button>
          </form>
        </div>
      </dialog>
    </>
  );
}
