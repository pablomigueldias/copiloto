"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Icone } from "@/components/icones";
import { Erro, Vazio, dataLonga } from "@/components/ui";
import { api } from "@/lib/api";
import type { Questao, Resposta } from "@/lib/tipos";

/** Quantas tentativas antes de a resposta certa aparecer. */
const REVELAR_APOS = 2;

type Fase = "aguardando" | "errado" | "revelado" | "certo" | "adiada";

function alternativasDe(q: Questao): { letra: string; texto: string }[] {
  // No julgue-o-item o par C/E não está no banco: ele é o formato, não conteúdo.
  if (q.formato === "certo_errado") {
    return [
      { letra: "C", texto: "Certo" },
      { letra: "E", texto: "Errado" },
    ];
  }
  return q.alternativas;
}

function Alternativa({
  letra,
  texto,
  escolhida,
  correta,
  errada,
  travada,
  onClick,
}: {
  letra: string;
  texto: string;
  escolhida: boolean;
  correta: boolean;
  errada: boolean;
  travada: boolean;
  onClick: () => void;
}) {
  const destaque = correta || escolhida;
  const rotulo = correta
    ? "correta"
    : errada
      ? "errada"
      : escolhida
        ? "escolhida"
        : "";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={travada}
      className={`group relative flex w-full items-start gap-3 rounded-[10px] border px-[14px] py-[11px] text-left text-[15px] transition-colors ${
        destaque
          ? "border-[color-mix(in_srgb,var(--color-accent)_55%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_9%,transparent)]"
          : errada
            ? "border-divider bg-transparent opacity-45"
            : "border-[color-mix(in_srgb,var(--color-text)_14%,transparent)] hover:border-[color-mix(in_srgb,var(--color-text)_30%,transparent)] hover:bg-[color-mix(in_srgb,var(--color-text)_5%,transparent)]"
      } ${travada && !destaque ? "cursor-default" : ""}`}
    >
      <span
        className={`tnum mt-px w-[18px] flex-none text-[13px] font-medium ${
          destaque ? "text-accent" : "text-neutral-500"
        }`}
      >
        {letra}
      </span>
      <span className="min-w-0 flex-1 leading-[1.5]">{texto}</span>
      {rotulo && (
        <span
          className={`mt-px flex-none text-[11px] ${
            correta ? "text-accent" : "text-neutral-500"
          }`}
        >
          {rotulo}
        </span>
      )}
    </button>
  );
}

function Revisao() {
  const params = useSearchParams();
  const topicoId = params.get("topico") ?? undefined;
  const moduloId = params.get("modulo") ?? undefined;
  const questaoId = params.get("questao") ?? undefined;
  // Treinar fora da data. O agendamento diz o mínimo que eu preciso rever, não
  // o máximo que eu posso — e abrir um tópico sem poder responder nada é a
  // tela dizendo não a quem quer estudar.
  const todas = params.get("todas") === "1";

  const [fila, setFila] = useState<Questao[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [i, setI] = useState(0);

  const [escolhida, setEscolhida] = useState<string | null>(null);
  const [erradas, setErradas] = useState<string[]>([]);
  const [tentativas, setTentativas] = useState(0);
  const [fase, setFase] = useState<Fase>("aguardando");
  const [resultado, setResultado] = useState<Resposta | null>(null);
  const [adiadaEm, setAdiadaEm] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const [certas, setCertas] = useState(0);
  const [errosSessao, setErrosSessao] = useState(0);
  // Zero até o efeito marcar: `Date.now()` no corpo do componente é leitura
  // impura, e um re-render mudaria o cronômetro no meio da questão.
  const abertaEm = useRef(0);

  useEffect(() => {
    let vivo = true;
    abertaEm.current = Date.now();
    api
      .fila({
        topico_id: topicoId,
        modulo_id: moduloId,
        questao_id: questaoId,
        todas: todas ? "true" : undefined,
        limite: todas || questaoId ? 100 : 24,
      })
      .then((f) => vivo && setFila(f.itens))
      .catch((e) => vivo && setErro(String(e.message ?? e)));
    return () => {
      vivo = false;
    };
  }, [topicoId, moduloId, questaoId, todas]);

  const q = fila?.[i];
  const alternativas = useMemo(() => (q ? alternativasDe(q) : []), [q]);
  const travada = fase === "certo" || fase === "revelado" || fase === "adiada";

  const limpar = useCallback(() => setFase("aguardando"), []);

  const escolher = useCallback(
    (letra: string) => {
      if (travada || erradas.includes(letra)) return;
      setEscolhida(letra);
      setFase("aguardando");
    },
    [travada, erradas],
  );

  const responder = useCallback(async () => {
    if (!q || !escolhida || enviando || travada) return;
    setEnviando(true);
    const n = tentativas + 1;
    try {
      const r = await api.responder(q.id, {
        resposta: escolhida,
        tentativa_n: n,
        segundos: Math.round((Date.now() - abertaEm.current) / 1000),
      });
      setResultado(r);
      setTentativas(n);
      if (r.acertou) {
        setCertas((c) => c + 1);
        setFase("certo");
      } else {
        setErrosSessao((c) => c + 1);
        setErradas((e) => [...e, escolhida]);
        setEscolhida(null);
        setFase(n >= REVELAR_APOS ? "revelado" : "errado");
      }
    } catch (e) {
      setErro(String((e as Error).message ?? e));
    } finally {
      setEnviando(false);
    }
  }, [q, escolhida, enviando, travada, tentativas]);

  const adiar = useCallback(async () => {
    if (!q || enviando) return;
    setEnviando(true);
    try {
      const r = await api.adiar(q.id);
      setAdiadaEm(r.proxima_em);
      setFase("adiada");
    } catch (e) {
      setErro(String((e as Error).message ?? e));
    } finally {
      setEnviando(false);
    }
  }, [q, enviando]);

  const proxima = useCallback(() => {
    setEscolhida(null);
    setErradas([]);
    setTentativas(0);
    setResultado(null);
    setAdiadaEm(null);
    setFase("aguardando");
    abertaEm.current = Date.now();
    setI((n) => n + 1);
  }, []);

  // Atalhos: A–E (ou C/E), Enter responde ou avança, P adia. Revisar de teclado
  // é a diferença entre 24 questões em 12 minutos e em 25.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const alvo = e.target as HTMLElement | null;
      if (alvo && ["INPUT", "TEXTAREA"].includes(alvo.tagName)) return;
      const k = e.key.toUpperCase();

      if (fase === "aguardando" || fase === "errado") {
        if (alternativas.some((a) => a.letra === k)) {
          e.preventDefault();
          escolher(k);
          return;
        }
        if (e.key === "Enter") {
          e.preventDefault();
          void responder();
          return;
        }
        if (k === "P") {
          e.preventDefault();
          void adiar();
        }
      } else if (e.key === "Enter") {
        e.preventDefault();
        proxima();
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [fase, alternativas, escolher, responder, adiar, proxima]);

  if (erro) {
    return (
      <div className="px-[clamp(24px,4vw,56px)] py-[34px]">
        <Erro>{erro}</Erro>
      </div>
    );
  }

  if (!fila) {
    return (
      <div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">
        montando a fila…
      </div>
    );
  }

  if (fila.length === 0 || i >= fila.length) {
    const total = fila.length;
    return (
      <div className="max-w-[720px] px-[clamp(24px,4vw,56px)] py-[44px]">
        {total === 0 ? (
          <Vazio
            titulo="Nada vence hoje"
            acao={{ href: "/modulos", rotulo: "Escolher um módulo" }}
          >
            Nenhuma questão está agendada para hoje. O que você acertou volta em
            sete dias, o que errou volta em dois — e em Módulos dá para{" "}
            <strong className="font-medium text-text">fazer as questões</strong>{" "}
            de um tópico fora da data, se quiser treinar mesmo assim.
          </Vazio>
        ) : (
          <>
            <h1 className="tnum m-0 mb-3 text-[clamp(32px,4vw,44px)] leading-[1.06] tracking-[-0.02em]">
              Sessão fechada
            </h1>
            <p className="m-0 mb-6 max-w-[46ch] text-[15px] text-muted">
              {certas} de {total} de primeira, {errosSessao}{" "}
              {errosSessao === 1 ? "erro" : "erros"}. As erradas voltam em dois
              dias — e voltam primeiro.
            </p>
            <div className="flex gap-2">
              <Link href="/" className="btn btn-primary px-[18px] py-[10px]">
                Voltar ao painel
                <Icone nome="seta" />
              </Link>
              <Link href="/modulos" className="btn btn-secondary py-[10px]">
                Outro módulo
              </Link>
            </div>
          </>
        )}
      </div>
    );
  }

  const progresso = ((i + (travada ? 1 : 0)) / fila.length) * 100;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center gap-[18px] px-[clamp(24px,4vw,56px)] pt-5">
        <div className="flex min-w-0 items-baseline gap-2 text-[12px] uppercase tracking-[0.06em]">
          <span className="text-accent">{q!.modulo}</span>
          <span className="text-neutral-700">/</span>
          <span className="truncate text-neutral-500">{q!.topico}</span>
        </div>
        <div className="ml-auto flex flex-none items-center gap-4">
          {(todas || questaoId) && (
            <span className="tag tag-outline flex-none">treino livre</span>
          )}
          <span className="tnum text-[12px] text-neutral-500">
            {i + 1} / {fila.length}
          </span>
          <button
            type="button"
            onClick={adiar}
            disabled={enviando || travada}
            className="btn btn-secondary px-3 py-[6px] text-[13px]"
          >
            Adiar — está fácil
          </button>
        </div>
      </header>

      <div className="mt-[18px] h-[2px] bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
        <div
          className="h-[2px] bg-accent transition-[width] duration-300"
          style={{ width: `${progresso}%` }}
        />
      </div>

      <div className="flex-1 px-[clamp(24px,4vw,56px)] pb-16 pt-11">
        <div className="max-w-[720px]">
          {q!.comando && (
            <p className="m-0 mb-4 text-[14px] leading-[1.55] text-muted">
              {q!.comando}
            </p>
          )}

          {q!.texto_base && (
            <div className="mb-4 border-l-2 border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] pl-4">
              <p className="m-0 text-[15px] leading-[1.6] text-muted">
                {q!.texto_base}
              </p>
              {q!.texto_base_fonte && (
                <p className="m-0 mt-1 text-[12px] text-neutral-600">
                  {q!.texto_base_fonte}
                </p>
              )}
            </div>
          )}

          {q!.codigo && (
            <pre className="mb-4 overflow-x-auto rounded-[8px] border border-divider bg-[color-mix(in_srgb,black_25%,transparent)] p-[14px] font-mono text-[13px] leading-[1.6]">
              {q!.codigo}
            </pre>
          )}

          <p className="m-0 mb-4 whitespace-pre-line text-[19px] leading-[1.5] tracking-[-0.005em]">
            {q!.enunciado}
          </p>

          {q!.afirmacoes.length > 0 && (
            <ol className="m-0 mb-4 flex list-[upper-roman] flex-col gap-[10px] pl-[30px] text-[15.5px] leading-[1.55] text-[color-mix(in_srgb,var(--color-text)_88%,transparent)]">
              {q!.afirmacoes.map((a, n) => (
                <li key={n}>{a}</li>
              ))}
            </ol>
          )}

          <div className="flex flex-col gap-2">
            {alternativas.map((a) => (
              <Alternativa
                key={a.letra}
                letra={a.letra}
                texto={a.texto}
                escolhida={escolhida === a.letra}
                correta={
                  travada && resultado?.gabarito === a.letra && fase !== "adiada"
                }
                errada={erradas.includes(a.letra)}
                travada={travada}
                onClick={() => escolher(a.letra)}
              />
            ))}
          </div>

          {(fase === "revelado" || fase === "certo") && (
            <div className="mt-5 rounded-[10px] border border-divider bg-surface p-4">
              <div className="card-kicker mb-[6px]">Por quê</div>
              {resultado?.explicacao ? (
                <p className="m-0 text-[14.5px] leading-[1.6] text-muted">
                  {resultado.explicacao}
                </p>
              ) : (
                <p className="m-0 text-[14px] leading-[1.6] text-neutral-500">
                  Esta questão ainda não tem explicação. A banca publica
                  gabarito, não justificativa — escreva a sua em{" "}
                  <Link
                    href={`/modulos?questao=${q!.id}`}
                    className="text-accent-300 underline underline-offset-2"
                  >
                    Módulos
                  </Link>{" "}
                  e ela aparece aqui na próxima volta.
                </p>
              )}
              {q!.origem && (
                <p className="m-0 mt-3 text-[12px] text-neutral-600">
                  Fonte: {q!.origem}
                </p>
              )}
            </div>
          )}

          <div className="mt-6">
            {fase === "aguardando" && (
              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={responder}
                  disabled={!escolhida || enviando}
                  className="btn btn-primary px-[18px] py-[10px] text-[15px]"
                >
                  {enviando ? "…" : "Responder"}
                </button>
                <button
                  type="button"
                  onClick={adiar}
                  disabled={enviando}
                  className="btn btn-ghost"
                >
                  Adiar por um mês
                </button>
                <span className="text-[12px] text-neutral-600">
                  {escolhida
                    ? `Alternativa ${escolhida} escolhida · Enter responde`
                    : "Escolha uma alternativa · teclas " +
                      alternativas.map((a) => a.letra).join(", ")}
                </span>
              </div>
            )}

            {fase === "errado" && (
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-[15px] font-medium text-accent-300">
                  Errado.
                </span>
                <span className="text-[13.5px] text-muted">
                  Tente de novo — a resposta só aparece depois da segunda
                  tentativa.
                </span>
                <button
                  type="button"
                  onClick={limpar}
                  className="btn btn-secondary py-[6px] text-[13px]"
                >
                  Tentar de novo
                </button>
              </div>
            )}

            {travada && (
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="text-[15px] font-medium">
                    {fase === "certo"
                      ? "Certo."
                      : fase === "adiada"
                        ? "Adiada."
                        : "Errado — esta é a resposta."}
                  </div>
                  <div className="tnum mt-px text-[13px] text-muted">
                    {fase === "adiada" && adiadaEm
                      ? `Sai da fila e volta em ${dataLonga(adiadaEm)} — um mês.`
                      : resultado
                        ? `Volta em ${resultado.intervalo_dias} ${
                            resultado.intervalo_dias === 1 ? "dia" : "dias"
                          }, ${dataLonga(resultado.proxima_em)}${
                            resultado.acertou
                              ? ", no mesmo tópico."
                              : ", e repete até sair certa."
                          }`
                        : ""}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={proxima}
                  className="btn btn-primary px-[18px] py-[10px] text-[15px]"
                >
                  {i + 1 >= fila.length ? "Fechar sessão" : "Próxima"}
                  <Icone nome="seta" tamanho={15} />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="px-[clamp(24px,4vw,56px)] py-[34px] text-[13px] text-neutral-500">
          montando a fila…
        </div>
      }
    >
      <Revisao />
    </Suspense>
  );
}
