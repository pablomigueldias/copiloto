"use client";

import { useEffect } from "react";

import { MUTOU } from "./api";

/**
 * Recarrega os contadores da tela quando eles podem ter mudado.
 *
 * Dois gatilhos, e cada um vê o que o outro não vê:
 *
 * - **o canal `MUTOU`**, onde o cliente da API anuncia toda escrita. Pega tanto
 *   o que outro componente desta aba escreveu — a tira de bancas, a gaveta da
 *   questão, o diálogo de apagar o tópico — quanto o que foi escrito em **outra
 *   aba**. Era o que faltava em 17/09/2026: 24 questões respondidas na aba da
 *   revisão, e o card de Módulos na outra aba ainda dizendo "108 hoje".
 * - **voltar para a aba**, que pega o que mudou sem passar por esta tela
 *   nenhuma: o `scripts/importar_questoes.py` que acabou de rodar, ou o dia que
 *   virou enquanto a aba dormia.
 *
 * `carregar` precisa ser estável (`useCallback`) — é ela que entra e sai como
 * ouvinte.
 */
export function useAtualizar(carregar: () => void) {
  useEffect(() => {
    const canal = new BroadcastChannel(MUTOU);
    canal.onmessage = () => carregar();

    // Só quando a aba fica visível: `visibilitychange` também avisa a saída, e
    // buscar contadores para uma tela que ninguém está vendo é gasto puro.
    const aoVoltar = () => {
      if (document.visibilityState === "visible") carregar();
    };
    document.addEventListener("visibilitychange", aoVoltar);

    return () => {
      canal.close();
      document.removeEventListener("visibilitychange", aoVoltar);
    };
  }, [carregar]);
}
