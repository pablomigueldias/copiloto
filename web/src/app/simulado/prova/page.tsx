"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { Dialogo } from "@/components/Dialogo";
import { Icone } from "@/components/icones";
import { CorpoQuestao, Opcao } from "@/components/simulado/Questao";
import { Erro } from "@/components/ui";
import { api } from "@/lib/api";
import type { ItemSimulado, SimuladoDetalhe } from "@/lib/tipos";

/** A prova real dá 4 h, com a discursiva dentro. */
const DURACAO_MIN = 240;

function decorrido(desde: string, agora: number): string {
  const min = Math.max(0, Math.floor((agora - new Date(desde).getTime()) / 60_000));
  const h = Math.floor(min / 60);
  return h ? `${h}h ${String(min % 60).padStart(2, "0")}min` : `${min} min`;
}

/** A folha de respostas: as 60 bolinhas, por matéria. */
function Folha({
  itens,
  atual,
  irPara,
}: {
  itens: ItemSimulado[];
  atual: number;
  irPara: (i: number) => void;
}) {
  const blocos = useMemo(() => {
    const b: { nome: string; itens: { item: ItemSimulado; i: number }[] }[] = [];
    itens.forEach((item, i) => {
      const ultimo = b[b.length - 1];
      if (ultimo && ultimo.nome === item.materia_nome) ultimo.itens.push({ item, i });
      else b.push({ nome: item.materia_nome, itens: [{ item, i }] });
    });
    return b;
  }, [itens]);

  return (
    <div className="flex flex-col gap-4">
      {blocos.map((b) => (
        <div key={b.nome}>
          <div className="mb-[6px] text-[11px] uppercase tracking-[0.08em] text-neutral-500">{b.nome}</div>
          <div className="flex flex-wrap gap-[5px]">
            {b.itens.map(({ item, i }) => (
              <button
                key={item.ordem}
                type="button"
                onClick={() => irPara(i)}
                aria-label={`Questão ${item.ordem}${item.resposta ? `, marcada ${item.resposta}` : ", em branco"}`}
                className={`tnum h-[30px] w-[38px] rounded-[6px] border text-[12px] transition-colors ${
                  item.resposta
                    ? "border-transparent bg-[color-mix(in_srgb,var(--color-accent)_16%,transparent)] text-text"
                    : "border-[color-mix(in_srgb,var(--color-text)_14%,transparent)] text-neutral-500 hover:text-text"
                } ${i === atual ? "outline outline-2 outline-offset-1 outline-accent" : ""}`}
              >
                {item.ordem}
                {item.resposta ? <span className="text-accent">{item.resposta}</span> : null}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Prova() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id") ?? "";
  const [sim, setSim] = useState<SimuladoDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [i, setI] = useState(0);
  const [agora, setAgora] = useState(0);
  const [confirmando, setConfirmando] = useState(false);
  const [entregando, setEntregando] = useState(false);

  useEffect(() => {
    let vivo = true;
    api
      .caderno(id)
      .then((s) => {
        if (!vivo) return;
        if (s.estado === "finalizado") {
          router.replace(`/simulado/resultado?id=${s.id}`);
          return;
        }
        setSim(s);
        // Volta na primeira em branco: quem saiu no meio continua de onde parou.
        const branca = s.itens.findIndex((it) => !it.resposta);
        setI(branca === -1 ? 0 : branca);
      })
      .catch((e) => vivo && setErro(String(e.message ?? e)));
    return () => {
      vivo = false;
    };
  }, [id, router]);

  // O relógio entra pelo callback do timer, nunca no corpo do efeito: a
  // primeira leitura vem em 1 s, e depois a cada 30.
  useEffect(() => {
    const primeiro = setTimeout(() => setAgora(Date.now()), 1_000);
    const t = setInterval(() => setAgora(Date.now()), 30_000);
    return () => {
      clearTimeout(primeiro);
      clearInterval(t);
    };
  }, []);

  const item = sim?.itens[i];
  const total = sim?.itens.length ?? 0;
  const brancas = sim ? sim.itens.filter((it) => !it.resposta).length : 0;

  const marcar = useCallback(
    async (letra: string) => {
      if (!sim || !item) return;
      // Clicar na marcada desmarca — apagar a bolinha também existe no papel.
      const nova = item.resposta === letra ? null : letra;
      const antes = item.resposta;
      setSim({
        ...sim,
        itens: sim.itens.map((it) => (it.ordem === item.ordem ? { ...it, resposta: nova } : it)),
      });
      try {
        await api.marcar(sim.id, item.ordem, nova);
      } catch (e) {
        setErro(String((e as Error).message ?? e));
        setSim((s) =>
          s && {
            ...s,
            itens: s.itens.map((it) => (it.ordem === item.ordem ? { ...it, resposta: antes } : it)),
          },
        );
      }
    },
    [sim, item],
  );

  const irPara = useCallback((n: number) => {
    setI(Math.max(0, Math.min(n, total - 1)));
    window.scrollTo({ top: 0 });
  }, [total]);

  async function entregar() {
    if (!sim) return;
    setEntregando(true);
    try {
      await api.entregar(sim.id);
      router.push(`/simulado/resultado?id=${sim.id}`);
    } catch (e) {
      setErro(String((e as Error).message ?? e));
      setEntregando(false);
      setConfirmando(false);
    }
  }

  // A–E marcam, ← → navegam. Prova de 60 questões feita no mouse cansa à toa.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (confirmando || e.metaKey || e.ctrlKey || e.altKey || !item) return;
      const alvo = e.target as HTMLElement | null;
      if (alvo && ["INPUT", "TEXTAREA"].includes(alvo.tagName)) return;
      const k = e.key.toUpperCase();
      if (item.questao.alternativas.some((a) => a.letra === k)) {
        e.preventDefault();
        void marcar(k);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        irPara(i + 1);
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        irPara(i - 1);
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [confirmando, item, marcar, irPara, i]);

  if (erro) {
    return (
      <div className="px-[clamp(24px,4vw,56px)] py-[34px]">
        <Erro>{erro}</Erro>
      </div>
    );
  }
  if (!sim || !item) {
    return <div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">abrindo o caderno…</div>;
  }

  const passou = agora ? (agora - new Date(sim.iniciado_em).getTime()) / 60_000 : 0;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-x-[18px] gap-y-2 px-[clamp(24px,4vw,56px)] pt-5">
        <div className="flex min-w-0 items-baseline gap-2 text-[12px] uppercase tracking-[0.06em]">
          <span className="text-accent">Simulado nº {sim.numero}</span>
          <span className="text-neutral-700">/</span>
          <span className="truncate text-neutral-500">{item.materia_nome}</span>
        </div>
        <div className="ml-auto flex flex-none items-center gap-4">
          <span
            className={`tnum text-[12px] ${passou > DURACAO_MIN ? "text-accent-300" : "text-neutral-500"}`}
            title="A prova real dá 4 h, incluída a discursiva"
          >
            {agora ? `${decorrido(sim.iniciado_em, agora)} de 4h` : "4h de prova"}
          </span>
          <span className="tnum text-[12px] text-neutral-500">
            {item.ordem} / {total}
          </span>
          <button
            type="button"
            onClick={() => setConfirmando(true)}
            className="btn btn-secondary px-3 py-[6px] text-[13px]"
          >
            Entregar a prova
          </button>
        </div>
      </header>

      <div className="mt-[18px] h-[2px] bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
        <div
          className="h-[2px] bg-accent transition-[width] duration-300"
          style={{ width: `${((total - brancas) / total) * 100}%` }}
        />
      </div>

      <div className="grid flex-1 gap-10 px-[clamp(24px,4vw,56px)] pb-16 pt-10 lg:grid-cols-[minmax(0,720px)_280px]">
        <div className="min-w-0">
          <div className="tnum mb-3 text-[13px] text-neutral-500">Questão {item.ordem}</div>
          <CorpoQuestao q={item.questao} />
          <div className="flex flex-col gap-2">
            {item.questao.alternativas.map((a) => (
              <Opcao
                key={a.letra}
                letra={a.letra}
                texto={a.texto}
                marca={item.resposta === a.letra ? "marcada" : "neutra"}
                onClick={() => void marcar(a.letra)}
              />
            ))}
          </div>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button type="button" onClick={() => irPara(i - 1)} disabled={i === 0} className="btn btn-secondary py-[9px]">
              Anterior
            </button>
            {i + 1 < total ? (
              <button type="button" onClick={() => irPara(i + 1)} className="btn btn-primary px-[18px] py-[9px]">
                Próxima
                <Icone nome="seta" tamanho={15} />
              </button>
            ) : (
              <button type="button" onClick={() => setConfirmando(true)} className="btn btn-primary px-[18px] py-[9px]">
                Entregar a prova
              </button>
            )}
            <span className="text-[12px] text-neutral-600">
              teclas {item.questao.alternativas.map((a) => a.letra).join(", ")} marcam · ← → navegam · clicar
              na marcada desmarca
            </span>
          </div>
        </div>

        <aside className="lg:sticky lg:top-6 lg:self-start">
          <div className="card-kicker mb-3">Folha de respostas</div>
          <Folha itens={sim.itens} atual={i} irPara={irPara} />
          <p className="tnum m-0 mt-4 text-[12.5px] text-muted">
            {total - brancas} marcadas · {brancas} em branco
          </p>
        </aside>
      </div>

      {confirmando && (
        <Dialogo
          titulo="Entregar a prova?"
          descricao={
            brancas
              ? `${brancas} ${brancas === 1 ? "questão está" : "questões estão"} em branco, e em branco conta como erro. Depois de entregar não dá para mudar nenhuma resposta.`
              : "Todas marcadas. Depois de entregar não dá para mudar nenhuma resposta."
          }
          confirmar={entregando ? "corrigindo…" : "entregar e ver a nota"}
          desabilitado={entregando}
          onConfirmar={() => void entregar()}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">abrindo o caderno…</div>}>
      <Prova />
    </Suspense>
  );
}
