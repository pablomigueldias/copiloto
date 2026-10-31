"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Icone } from "@/components/icones";
import { api, ApiErro } from "@/lib/api";
import type { ReforcoResumo } from "@/lib/tipos";

/**
 * O que a linha de um assunto mostra à direita, conforme o reforço está:
 * gerar → gerando… → fazer as 5 → aprovado/reprovado.
 *
 * A escrita roda fora da tela (Claude Code sem cabeça, alguns minutos por
 * assunto); quem acompanha é o polling de quem monta a lista
 * (`useAtualizarEnquantoGera`).
 */
export function AcaoReforco({
  r,
  onMudou,
}: {
  r: ReforcoResumo;
  onMudou: () => void;
}) {
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function gerar() {
    setEnviando(true);
    setErro(null);
    try {
      await api.gerarReforco(r.id);
      onMudou();
    } catch (e) {
      setErro(e instanceof ApiErro ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  if (r.estado === "pronto") {
    return (
      <Link href={`/simulado/reforco?id=${r.id}`} className="btn btn-primary px-[14px] py-[7px] text-[13px]">
        {r.respondidas ? `Continuar (${r.respondidas}/${r.total})` : `Fazer as ${r.total}`}
        <Icone nome="seta" tamanho={14} />
      </Link>
    );
  }
  if (r.estado === "aprovado" || r.estado === "reprovado") {
    return (
      <span className={`text-[12.5px] ${r.estado === "aprovado" ? "text-accent" : "text-neutral-500"}`}>
        {r.estado === "aprovado" ? "aprovado" : `reprovado na rodada ${r.rodada}`} · {r.acertos}/{r.total}
      </span>
    );
  }
  if (r.geracao === "gerando") {
    return (
      <span className="flex items-center gap-2 text-[12.5px] text-muted" title="Escrevendo as 5 questões e conferindo o gabarito. Leva alguns minutos.">
        <span className="inline-block h-[10px] w-[10px] animate-spin rounded-full border-2 border-accent border-t-transparent" />
        gerando as 5…
      </span>
    );
  }
  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => void gerar()}
        disabled={enviando}
        className="btn btn-secondary px-[14px] py-[7px] text-[13px]"
      >
        {enviando ? "…" : r.geracao === "erro" ? "Tentar de novo" : "Gerar reforço"}
      </button>
      {(erro || (r.geracao === "erro" && r.geracao_erro)) && (
        <span className="max-w-[46ch] text-right text-[11.5px] leading-[1.4] text-accent-300" title={erro ?? r.geracao_erro ?? ""}>
          {(erro ?? r.geracao_erro ?? "").slice(-160)}
        </span>
      )}
    </div>
  );
}

/** Recarrega a cada 8 s enquanto algum reforço estiver sendo gerado. */
export function useAtualizarEnquantoGera(reforcos: ReforcoResumo[] | undefined, recarregar: () => void) {
  const gerando = !!reforcos?.some((r) => r.geracao === "gerando");
  useEffect(() => {
    if (!gerando) return;
    const t = setInterval(recarregar, 8_000);
    return () => clearInterval(t);
  }, [gerando, recarregar]);
}

/** "Gerar todos": dispara os que esperam e não estão sendo gerados. */
export function GerarTodos({ reforcos, onMudou }: { reforcos: ReforcoResumo[]; onMudou: () => void }) {
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const faltam = reforcos.filter((r) => r.estado === "aguardando_questoes" && r.geracao !== "gerando").length;
  if (!faltam) return null;

  async function gerar() {
    setEnviando(true);
    setErro(null);
    try {
      await api.gerarTodosReforcos();
      onMudou();
    } catch (e) {
      setErro(e instanceof ApiErro ? e.message : String(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" onClick={() => void gerar()} disabled={enviando} className="btn btn-primary px-[16px] py-[8px] text-[13.5px]">
        {enviando ? "…" : `Gerar todos (${faltam})`}
      </button>
      <span className="text-[12.5px] text-muted">
        Cada assunto leva alguns minutos; três são escritos ao mesmo tempo. Pode sair da tela.
      </span>
      {erro && <span className="text-[12.5px] text-accent-300">{erro}</span>}
    </div>
  );
}
