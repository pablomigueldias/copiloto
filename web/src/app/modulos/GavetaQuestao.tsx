"use client";

import { useEffect, useState } from "react";

import { quando } from "@/components/ui";
import { api } from "@/lib/api";
import type { Questao, Tentativa } from "@/lib/tipos";

/**
 * A gaveta de uma questão: o conteúdo, o histórico e o campo de explicação.
 *
 * Quem monta passa `key={questao.id}`: trocar de questão **remonta** o
 * componente e o campo nasce com o texto certo. A alternativa — sincronizar o
 * estado com a prop num efeito — é o anti-padrão que a própria documentação do
 * React manda resolver com key.
 *
 * É por aqui que a explicação entra. O acervo importado dos PDFs vem sem
 * justificativa — as bancas publicam gabarito, não razão — e escrever uma e
 * apresentá-la como delas seria inventar fonte. A minha explicação, escrita
 * depois de errar, aparece na próxima volta da questão.
 */
export function GavetaQuestao({
  questao,
  onFechar,
  onSalvo,
}: {
  questao: Questao;
  onFechar: () => void;
  onSalvo: (q: Questao) => void;
}) {
  const [explicacao, setExplicacao] = useState(questao.explicacao ?? "");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [historico, setHistorico] = useState<Tentativa[] | null>(null);

  useEffect(() => {
    let vivo = true;
    api
      .historico(questao.id)
      .then((h) => vivo && setHistorico(h))
      .catch(() => vivo && setHistorico([]));
    return () => {
      vivo = false;
    };
  }, [questao.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onFechar();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onFechar]);

  const salvar = async () => {
    setSalvando(true);
    setErro(null);
    try {
      onSalvo(
        await api.editarQuestao(questao.id, {
          explicacao: explicacao.trim() || null,
        }),
      );
    } catch (e) {
      setErro(String((e as Error).message ?? e));
    } finally {
      setSalvando(false);
    }
  };

  const a = questao.agenda;
  const respondidas = a ? a.total_acertos + a.total_erros : 0;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[rgb(0_0_0/55%)]"
      onClick={onFechar}
    >
      <aside
        className="elev-lg flex h-full w-[min(560px,100%)] flex-col overflow-y-auto border-l border-divider bg-bg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-divider bg-bg px-6 py-4">
          <div className="min-w-0 text-[11px] uppercase tracking-[0.08em]">
            <span className="text-accent">{questao.modulo}</span>
            <span className="mx-1 text-neutral-700">/</span>
            <span className="text-neutral-500">{questao.topico}</span>
          </div>
          <button
            type="button"
            onClick={onFechar}
            className="btn btn-ghost ml-auto px-2 py-1 text-[13px]"
          >
            fechar
          </button>
        </header>

        <div className="flex flex-col gap-5 px-6 py-5">
          {questao.comando && (
            <p className="m-0 text-[13.5px] leading-[1.55] text-muted">
              {questao.comando}
            </p>
          )}

          <p className="m-0 whitespace-pre-line text-[16px] leading-[1.55]">
            {questao.enunciado}
          </p>

          {questao.alternativas.length > 0 && (
            <div className="flex flex-col gap-[6px]">
              {questao.alternativas.map((alt) => (
                <div
                  key={alt.letra}
                  className={`flex gap-3 rounded-[8px] px-3 py-2 text-[14px] ${
                    alt.letra === questao.gabarito
                      ? "bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)] text-accent-200"
                      : "text-muted"
                  }`}
                >
                  <span className="tnum w-[16px] flex-none text-[13px]">
                    {alt.letra}
                  </span>
                  <span>{alt.texto}</span>
                </div>
              ))}
            </div>
          )}

          <div className="tnum text-[12.5px] text-neutral-500">
            gabarito{" "}
            <span className="text-accent">{questao.gabarito}</span> ·
            dificuldade {questao.dificuldade} ·{" "}
            {questao.formato.replace("_", " ")}
          </div>

          {questao.origem && (
            <p className="m-0 text-[12px] leading-[1.5] text-neutral-600">
              {questao.origem}
            </p>
          )}

          <hr className="hr" />

          <div>
            <label
              htmlFor="explicacao"
              className="card-kicker mb-2 block text-neutral-400"
            >
              Explicação — o &ldquo;por quê&rdquo; que aparece na revisão
            </label>
            <textarea
              id="explicacao"
              className="input min-h-[130px] resize-y leading-[1.55]"
              value={explicacao}
              onChange={(e) => setExplicacao(e.target.value)}
              placeholder="Por que a correta está correta e, quando ajuda, por que a mais tentadora não está."
            />
            <p className="m-0 mt-2 text-[12px] leading-[1.5] text-neutral-600">
              Veio vazia de propósito: a banca publicou o gabarito, não a razão.
              Esta explicação é sua.
            </p>
            {erro && (
              <p className="m-0 mt-2 text-[12.5px] text-accent-300">{erro}</p>
            )}
            <button
              type="button"
              onClick={salvar}
              disabled={salvando || explicacao === (questao.explicacao ?? "")}
              className="btn btn-primary mt-3"
            >
              {salvando ? "salvando…" : "Salvar explicação"}
            </button>
          </div>

          <hr className="hr" />

          <div>
            <div className="card-kicker mb-2 text-neutral-400">Histórico</div>
            {a && (
              <div className="tnum mb-3 text-[13px] text-muted">
                {respondidas === 0
                  ? "Nunca respondida."
                  : `${a.total_acertos} de ${respondidas} certas · ${a.acertos_seguidos} seguidas · estado ${a.estado}`}
                {" · volta "}
                {quando(a.proxima_em)}
              </div>
            )}
            {!historico ? (
              <p className="m-0 text-[13px] text-neutral-600">carregando…</p>
            ) : historico.length === 0 ? (
              <p className="m-0 text-[13px] text-neutral-600">
                Sem tentativas ainda.
              </p>
            ) : (
              <ul className="m-0 flex list-none flex-col gap-[6px] p-0">
                {historico.map((t) => (
                  <li
                    key={t.id}
                    className="tnum flex items-center gap-3 text-[13px]"
                  >
                    <span
                      className={`h-[6px] w-[6px] flex-none rounded-full ${
                        t.acertou ? "bg-accent" : "bg-neutral-600"
                      }`}
                    />
                    <span className="text-muted">
                      {new Intl.DateTimeFormat("pt-BR", {
                        day: "2-digit",
                        month: "2-digit",
                        year: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      }).format(new Date(t.respondida_em))}
                    </span>
                    <span
                      className={t.acertou ? "text-accent-300" : "text-neutral-500"}
                    >
                      {t.acertou ? "certo" : "errado"}
                    </span>
                    <span className="text-neutral-600">
                      marcou {t.resposta}
                      {t.tentativa_n > 1 ? ` · ${t.tentativa_n}ª tentativa` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
