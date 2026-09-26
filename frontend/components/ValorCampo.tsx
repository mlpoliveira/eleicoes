import type { Campo } from "@/lib/api";
import { formatarCampo, NAO_DISPONIVEL } from "@/lib/formato";
import { SeloNatureza } from "./SeloNatureza";
import { VerFonte } from "./VerFonte";

interface Props {
  nome: string;
  rotulo: string;
  campo: Campo;
  sq?: number;
}

// Linha "rótulo: valor [NATUREZA] Ver fonte". Ausência aparece por extenso, nunca como 0.
export function ValorCampo({ nome, rotulo, campo, sq }: Props) {
  const ausente = campo.valor === null || campo.valor === undefined;
  return (
    <div className="grid grid-cols-[minmax(8rem,38%)_1fr] gap-3 border-b border-borda py-2 last:border-0">
      <dt className="text-sm text-texto-2">{rotulo}</dt>
      <dd className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span className={`break-words [overflow-wrap:anywhere] ${ausente ? "ausente" : ""}`}>
          {ausente ? NAO_DISPONIVEL : formatarCampo(nome, campo.valor)}
        </span>
        <SeloNatureza natureza={campo.natureza} />
        <VerFonte
          consulta={sq ? { tabela: "candidato", sq, campo: nome } : undefined}
          fonte={campo.fonte}
          geracao={campo.geracao_tse}
          observacao={campo.observacao}
        />
      </dd>
    </div>
  );
}
