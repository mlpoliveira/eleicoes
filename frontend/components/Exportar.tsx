import { montarQuery } from "@/lib/api";

type Params = Record<string, string | number | boolean | (string | number)[] | null | undefined>;

// Links de download (T8): o backend gera o arquivo com os mesmos filtros da tela + metadados.
export function Exportar({ caminho, params }: { caminho: string; params: Params }) {
  const url = (formato: string) => `/api/exportar/${caminho}${montarQuery({ ...params, formato })}`;
  return (
    <span className="inline-flex items-center gap-2 text-xs">
      <span className="text-texto-3">Exportar:</span>
      <a href={url("csv")} download className="rounded border border-borda px-2 py-0.5 hover:bg-superficie-2">CSV</a>
      <a href={url("xlsx")} download className="rounded border border-borda px-2 py-0.5 hover:bg-superficie-2">Excel</a>
    </span>
  );
}
