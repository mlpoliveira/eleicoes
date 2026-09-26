"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SeletorCarga, useCargas, type InfoCarga } from "@/lib/cargas";
import { numero } from "@/lib/formato";
import { Carregando, Erro } from "@/components/Estado";
import { SeloNatureza } from "@/components/SeloNatureza";

interface Verificacao {
  verificacao: string;
  quantidade: number;
  quantidade_anterior: number | null;
  variacao: number | null;
  explicacao: string | null;
}
interface Resposta {
  descricao: string;
  carga: InfoCarga;
  carga_anterior: InfoCarga | null;
  verificacoes: Verificacao[];
}

function Variacao({ v }: { v: number | null }) {
  if (v === null) return <span className="ausente text-xs">sem carga anterior</span>;
  if (v === 0) return <span className="whitespace-nowrap text-texto-3">igual</span>;
  return <span className="font-medium">{v > 0 ? "+" : "−"}{numero(Math.abs(v))}</span>;
}

export default function PaginaQualidade() {
  const cargas = useCargas();
  const [carga, setCarga] = useState("");
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    setR(null);
    api<Resposta>("/qualidade", { carga_id: carga }).then(setR).catch((e: Error) => setErro(e.message));
  }, [carga]);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Qualidade dos dados</h1>
        {r && <p className="mt-1 max-w-3xl text-sm text-texto-2">{r.descricao}</p>}
      </header>
      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-borda bg-superficie p-3">
        <SeletorCarga cargas={cargas} valor={carga} onChange={setCarga} />
        <Link href="/alteracoes" className="text-sm text-destaque hover:underline">Ver alterações desde a última atualização →</Link>
      </div>
      {erro && <Erro mensagem={erro} />}
      {!r && !erro && <Carregando />}
      {r && (
        <section className="rounded-lg border border-borda bg-superficie">
          <div className="border-b border-borda px-3 py-2 text-sm">
            Carga nº {r.carga.carga_id} · geração TSE <b>{r.carga.geracao_tse}</b>
            {r.carga_anterior ? <> · comparada com a carga nº {r.carga_anterior.carga_id} (geração {r.carga_anterior.geracao_tse})</>
              : <> · primeira carga do banco</>}
            <span className="ml-2"><SeloNatureza natureza="CALCULO" /></span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-superficie-2 text-left text-xs text-texto-2">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">Verificação</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Quantidade</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Carga anterior</th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">Variação</th>
                </tr>
              </thead>
              <tbody>
                {r.verificacoes.map((v) => (
                  <tr key={v.verificacao} className="border-t border-borda align-top">
                    <td className="px-3 py-2">
                      <div className="font-medium">{v.verificacao}</div>
                      {v.explicacao && <div className="mt-0.5 text-xs text-texto-2">{v.explicacao}</div>}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">{numero(v.quantidade)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {v.quantidade_anterior === null ? <span className="ausente text-xs">—</span> : numero(v.quantidade_anterior)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums"><Variacao v={v.variacao} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-borda px-3 py-2 text-xs text-texto-3">
            Arquivos lidos nesta carga: {r.carga.arquivos}. Carregada em {r.carga.carregada_em?.replace("T", " ").slice(0, 19)}.
          </p>
        </section>
      )}
    </div>
  );
}
