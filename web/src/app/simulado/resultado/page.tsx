"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { AcaoReforco, GerarTodos, useAtualizarEnquantoGera } from "@/components/simulado/GerarReforco";
import { CorpoQuestao, Corrigida, PorQue, nota } from "@/components/simulado/Questao";
import { Cabecalho, Erro, plural } from "@/components/ui";
import { api } from "@/lib/api";
import type { ReforcoResumo, ResultadoSimulado } from "@/lib/tipos";

function Resultado() {
  const id = useSearchParams().get("id") ?? "";
  const [res, setRes] = useState<ResultadoSimulado | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = useCallback(() => {
    api.resultado(id).then(setRes).catch((e) => setErro(String(e.message ?? e)));
  }, [id]);
  useEffect(carregar, [carregar]);
  useAtualizarEnquantoGera(res?.reforcos, carregar);

  if (erro) {
    return (
      <div className="px-[clamp(24px,4vw,56px)] py-[34px]">
        <Erro>{erro}</Erro>
      </div>
    );
  }
  if (!res) {
    return <div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">corrigindo…</div>;
  }

  // A rodada mais recente de cada assunto é a que diz onde ele está.
  const reforco = new Map<string, ReforcoResumo>();
  for (const r of res.reforcos) {
    const atual = reforco.get(r.assunto);
    if (!atual || r.rodada > atual.rodada) reforco.set(r.assunto, r);
  }
  const pendentes = [...reforco.values()].filter((r) => r.estado === "pronto" || r.estado === "aguardando_questoes");

  return (
    <div className="max-w-[860px] px-[clamp(24px,4vw,56px)] py-[34px]">
      <Link href="/simulado" className="text-[13px] text-neutral-500 no-underline hover:text-text">
        ← Simulado
      </Link>

      <div className="mb-10 mt-4 flex flex-wrap items-end gap-x-10 gap-y-4">
        <div>
          <div className="text-[12px] uppercase tracking-[0.08em] text-accent">Simulado nº {res.numero}</div>
          <div className="tnum font-heading text-[clamp(52px,7vw,76px)] font-medium leading-none tracking-[-0.03em]">
            {nota(res.nota)}
          </div>
        </div>
        <div className="pb-2 text-[14px] text-muted">
          <div className={`text-[15px] ${res.habilitado ? "text-accent" : "text-text"}`}>
            {res.habilitado ? "Habilitado na objetiva" : `Abaixo dos ${res.nota_minima} pontos`}
          </div>
          <div className="tnum mt-1">
            {res.acertos} de {res.total} · P = 100/{res.total} × {res.acertos} (edital, item 12.3)
          </div>
        </div>
      </div>

      <section className="mb-10">
        <Cabecalho>Por matéria</Cabecalho>
        <table className="tnum w-full border-collapse text-[14px]">
          <tbody>
            {res.por_materia.map((m) => (
              <tr key={m.chave} className="border-b border-divider">
                <td className="py-[10px]">{m.nome}</td>
                <td className="w-[90px] py-[10px] text-right text-muted">
                  {m.acertos}/{m.total}
                </td>
                <td className="w-[180px] py-[10px] pl-4">
                  <div className="h-[4px] overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
                    <div className="h-full bg-accent" style={{ width: `${m.percentual}%` }} />
                  </div>
                </td>
                <td className="w-[60px] py-[10px] text-right">{Math.round(m.percentual)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mb-10">
        <Cabecalho>O que reforçar</Cabecalho>
        {res.erros.length === 0 ? (
          <p className="m-0 text-[14px] text-muted">Nenhum erro. O próximo simulado está liberado.</p>
        ) : (
          <>
            <p className="m-0 mb-4 max-w-[62ch] text-[13.5px] text-muted">
              Cada assunto abaixo vira um reforço de 5 questões, com aprovação em{" "}
              {pendentes[0]?.minimo ?? 4} de 5 (75%). O próximo simulado abre quando todos passarem, e esses
              assuntos voltam nele.
            </p>
            <div className="flex flex-col gap-6">
              {res.por_materia
                .filter((m) => m.assuntos_errados.length)
                .map((m) => (
                  <div key={m.chave}>
                    <div className="mb-2 text-[12px] uppercase tracking-[0.08em] text-neutral-500">{m.nome}</div>
                    <ul className="card m-0 list-none py-1">
                      {m.assuntos_errados.map((a) => {
                        const r = reforco.get(a.assunto);
                        return (
                          <li
                            key={a.assunto}
                            className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-divider py-3 last:border-b-0"
                          >
                            <div className="min-w-0 flex-1">
                              <div className="text-[15px]">{a.assunto}</div>
                              <div className="tnum mt-px text-[12px] text-neutral-500">
                                {a.grupo} · errou {a.erros} de {a.total}
                              </div>
                            </div>
                            {r && <AcaoReforco r={r} onMudou={carregar} />}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ))}
            </div>
            <div className="mt-4">
              <GerarTodos reforcos={[...reforco.values()]} onMudou={carregar} />
            </div>
          </>
        )}
      </section>

      {res.erros.length > 0 && (
        <section>
          <Cabecalho>{plural(res.erros.length, "questão errada", "questões erradas")}</Cabecalho>
          <div className="flex flex-col gap-4">
            {res.erros.map((it) => (
              <details key={it.ordem} className="card group" open>
                <summary className="flex cursor-pointer list-none flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="tnum text-[13px] text-neutral-500">Questão {it.ordem}</span>
                  <span className="text-[15px]">{it.assunto}</span>
                  <span className="text-[12px] text-neutral-500">{it.materia_nome}</span>
                  {it.revisao && <span className="tag tag-outline">voltou por erro anterior</span>}
                  <span className="tnum ml-auto text-[12.5px] text-muted">
                    {it.resposta ? `marcou ${it.resposta}` : "em branco"} · gabarito {it.questao.gabarito}
                  </span>
                </summary>
                <div className="mt-5">
                  <CorpoQuestao q={it.questao} />
                  <Corrigida q={it.questao} resposta={it.resposta} />
                  <PorQue q={it.questao} />
                </div>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">corrigindo…</div>}>
      <Resultado />
    </Suspense>
  );
}
