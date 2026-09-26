// Seleção para comparar, guardada só no navegador (localStorage). Nunca é enviada nem usada
// para inferir preferência política (regra 7 do CLAUDE.md).
"use client";

import { useCallback, useEffect, useState } from "react";

export const MAX_COMPARAR = 5;
const CHAVE = "eleicoes2026:comparar";
const EVENTO = "eleicoes2026:comparar-mudou";

export interface Selecionado {
  sq: number;
  nome: string;
  cargo: string;
  uf: string;
}

function ler(): Selecionado[] {
  try {
    const v = JSON.parse(localStorage.getItem(CHAVE) ?? "[]");
    return Array.isArray(v) ? v.slice(0, MAX_COMPARAR) : [];
  } catch {
    return [];
  }
}

function gravar(lista: Selecionado[]) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify(lista));
  } catch {
    /* armazenamento indisponível: a seleção vale só nesta página */
  }
  window.dispatchEvent(new Event(EVENTO));
}

export function useComparacao() {
  const [lista, setLista] = useState<Selecionado[]>([]);
  useEffect(() => {
    const atualizar = () => setLista(ler());
    atualizar();
    window.addEventListener(EVENTO, atualizar);
    window.addEventListener("storage", atualizar);
    return () => {
      window.removeEventListener(EVENTO, atualizar);
      window.removeEventListener("storage", atualizar);
    };
  }, []);

  const adicionar = useCallback((s: Selecionado) => {
    const atual = ler();
    if (atual.some((x) => x.sq === s.sq) || atual.length >= MAX_COMPARAR) return;
    gravar([...atual, s]);
  }, []);
  const remover = useCallback((sq: number) => gravar(ler().filter((x) => x.sq !== sq)), []);
  const limpar = useCallback(() => gravar([]), []);
  const contem = useCallback((sq: number) => lista.some((x) => x.sq === sq), [lista]);

  return { lista, adicionar, remover, limpar, contem, cheio: lista.length >= MAX_COMPARAR };
}
