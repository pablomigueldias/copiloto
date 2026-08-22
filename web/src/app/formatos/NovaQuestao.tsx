"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ModuloResumo } from "@/lib/tipos";

const LETRAS = ["A", "B", "C", "D", "E"] as const;

const SEM_ALTERNATIVAS = ["certo_errado", "flashcard"];

/**
 * O formulário de cadastro. Uma gaveta, não uma página.
 *
 * O que ele valida do lado do cliente é só o que evita ida ao servidor sem
 * chance: cinco alternativas quando o formato pede cinco, gabarito dentro do
 * conjunto do formato. O resto é do backend — validação duplicada diverge, e a
 * que vale é sempre a de lá.
 */
export function NovaQuestao({
  formato,
  modulos,
  onFechar,
  onCriada,
}: {
  formato: string;
  modulos: ModuloResumo[];
  onFechar: () => void;
  onCriada: () => void;
}) {
  const topicos = modulos.flatMap((m) => m.topicos);
  const primeiroTopico = topicos[0]?.id ?? "";
  const [topicoId, setTopicoId] = useState(primeiroTopico);
  const [comando, setComando] = useState("");
  const [enunciado, setEnunciado] = useState("");
  const [textoBase, setTextoBase] = useState("");
  const [codigo, setCodigo] = useState("");
  const [afirmacoes, setAfirmacoes] = useState(["", "", ""]);
  const [alternativas, setAlternativas] = useState(["", "", "", "", ""]);
  const [gabarito, setGabarito] = useState(
    formato === "certo_errado" ? "C" : "A",
  );
  const [explicacao, setExplicacao] = useState("");
  const [dificuldade, setDificuldade] = useState(2);
  const [fonte, setFonte] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onFechar();
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [onFechar]);

  const precisaAlternativas = !SEM_ALTERNATIVAS.includes(formato);
  const opcoesGabarito = formato === "certo_errado" ? ["C", "E"] : LETRAS;

  const enviar = async () => {
    setErro(null);
    if (!topicoId) return setErro("Escolha um tópico.");
    if (!enunciado.trim()) return setErro("O enunciado é obrigatório.");
    if (precisaAlternativas && alternativas.some((a) => !a.trim())) {
      return setErro(
        "Prova de concurso tem cinco alternativas. Preencha as cinco.",
      );
    }

    setEnviando(true);
    try {
      await api.criarQuestao({
        topico_id: topicoId,
        formato,
        comando: comando.trim() || null,
        enunciado: enunciado.trim(),
        texto_base: textoBase.trim() || null,
        codigo: codigo.trim() || null,
        afirmacoes:
          formato === "afirmacoes"
            ? afirmacoes.filter((a) => a.trim()).map((a) => a.trim())
            : [],
        alternativas: precisaAlternativas
          ? LETRAS.map((l, i) => ({ letra: l, texto: alternativas[i].trim() }))
          : [],
        gabarito,
        explicacao: explicacao.trim() || null,
        fonte: fonte.trim() || null,
        dificuldade,
      });
      onCriada();
    } catch (e) {
      setErro(String((e as Error).message ?? e));
    } finally {
      setEnviando(false);
    }
  };

  const campo = "flex flex-col gap-[6px]";
  const rotulo = "card-kicker text-neutral-400";

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-[rgb(0_0_0/55%)]"
      onClick={onFechar}
    >
      <aside
        className="elev-lg flex h-full w-[min(620px,100%)] flex-col overflow-y-auto border-l border-divider bg-bg"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-divider bg-bg px-6 py-4">
          <h3 className="m-0 text-[17px]">Nova questão</h3>
          <span className="tag tag-outline">{formato.replace("_", " ")}</span>
          <button
            type="button"
            onClick={onFechar}
            className="btn btn-ghost ml-auto px-2 py-1 text-[13px]"
          >
            fechar
          </button>
        </header>

        <div className="flex flex-col gap-5 px-6 py-5">
          {topicos.length === 0 ? (
            <div className="card border-dashed">
              <h4 className="m-0 mb-2 text-[16px]">Não há tópico nenhum</h4>
              <p className="m-0 mb-3 text-[14px] text-muted">
                Questão não mora solta: ela nasce dentro de um tópico, e o
                tópico dentro de um módulo. Crie os dois em Módulos e volte.
              </p>
              <Link href="/modulos" className="btn btn-secondary">
                Ir para Módulos
              </Link>
            </div>
          ) : (
          <>
          <div className={campo}>
            <label className={rotulo} htmlFor="topico">
              Tópico
            </label>
            <select
              id="topico"
              className="input"
              value={topicoId}
              onChange={(e) => setTopicoId(e.target.value)}
            >
              {modulos.map((m) => (
                <optgroup key={m.id} label={m.nome}>
                  {m.topicos.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.nome}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          {formato === "certo_errado" && (
            <div className={campo}>
              <label className={rotulo} htmlFor="comando">
                Comando do bloco
              </label>
              <textarea
                id="comando"
                className="input min-h-[64px] resize-y"
                value={comando}
                onChange={(e) => setComando(e.target.value)}
                placeholder="Acerca da proposição “…”, julgue o item a seguir."
              />
            </div>
          )}

          {formato === "texto_base" && (
            <div className={campo}>
              <label className={rotulo} htmlFor="texto-base">
                Texto-base
              </label>
              <textarea
                id="texto-base"
                className="input min-h-[90px] resize-y"
                value={textoBase}
                onChange={(e) => setTextoBase(e.target.value)}
              />
            </div>
          )}

          {formato === "codigo" && (
            <div className={campo}>
              <label className={rotulo} htmlFor="codigo">
                Código
              </label>
              <textarea
                id="codigo"
                className="input min-h-[110px] resize-y font-mono text-[13px]"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
              />
            </div>
          )}

          <div className={campo}>
            <label className={rotulo} htmlFor="enunciado">
              {formato === "flashcard" ? "Frente" : "Enunciado"}
            </label>
            <textarea
              id="enunciado"
              className="input min-h-[90px] resize-y"
              value={enunciado}
              onChange={(e) => setEnunciado(e.target.value)}
              placeholder={
                formato === "negativa"
                  ? "…NÃO se trata de…  (o NÃO em maiúsculas, como na prova)"
                  : undefined
              }
            />
          </div>

          {formato === "afirmacoes" && (
            <div className={campo}>
              <span className={rotulo}>Afirmações I, II, III</span>
              {afirmacoes.map((a, i) => (
                <input
                  key={i}
                  className="input"
                  value={a}
                  placeholder={["I", "II", "III"][i]}
                  onChange={(e) =>
                    setAfirmacoes((v) =>
                      v.map((x, n) => (n === i ? e.target.value : x)),
                    )
                  }
                />
              ))}
            </div>
          )}

          {precisaAlternativas && (
            <div className={campo}>
              <span className={rotulo}>Alternativas — as cinco</span>
              {LETRAS.map((l, i) => (
                <div key={l} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setGabarito(l)}
                    aria-label={`marcar ${l} como gabarito`}
                    className={`tnum h-[30px] w-[30px] flex-none rounded-[6px] border text-[13px] transition-colors ${
                      gabarito === l
                        ? "border-[color-mix(in_srgb,var(--color-accent)_55%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent"
                        : "border-divider text-neutral-500 hover:text-text"
                    }`}
                  >
                    {l}
                  </button>
                  <input
                    className="input"
                    value={alternativas[i]}
                    onChange={(e) =>
                      setAlternativas((v) =>
                        v.map((x, n) => (n === i ? e.target.value : x)),
                      )
                    }
                  />
                </div>
              ))}
              <p className="m-0 text-[12px] text-neutral-600">
                A letra acesa é o gabarito.
              </p>
            </div>
          )}

          {!precisaAlternativas && (
            <div className={campo}>
              <span className={rotulo}>Gabarito</span>
              <div className="flex gap-2">
                {opcoesGabarito.map((l) => (
                  <button
                    key={l}
                    type="button"
                    onClick={() => setGabarito(l)}
                    className={`btn ${gabarito === l ? "btn-primary" : "btn-secondary"}`}
                  >
                    {l === "C" ? "Certo" : l === "E" ? "Errado" : l}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className={campo}>
            <label className={rotulo} htmlFor="explicacao-nova">
              {formato === "flashcard" ? "Verso" : "Explicação (opcional)"}
            </label>
            <textarea
              id="explicacao-nova"
              className="input min-h-[80px] resize-y"
              value={explicacao}
              onChange={(e) => setExplicacao(e.target.value)}
            />
          </div>

          <div className="flex gap-4">
            <div className={`${campo} flex-1`}>
              <label className={rotulo} htmlFor="fonte">
                Fonte
              </label>
              <input
                id="fonte"
                className="input"
                value={fonte}
                onChange={(e) => setFonte(e.target.value)}
                placeholder="nota do vault, prova, livro"
              />
            </div>
            <div className={campo}>
              <span className={rotulo}>Dificuldade</span>
              <div className="flex gap-1">
                {[1, 2, 3].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => setDificuldade(d)}
                    className={`btn ${dificuldade === d ? "btn-primary" : "btn-secondary"} px-3`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {erro && <p className="m-0 text-[13px] text-accent-300">{erro}</p>}

          <div className="flex items-center gap-3 pb-4">
            <button
              type="button"
              onClick={enviar}
              disabled={enviando}
              className="btn btn-primary px-4 py-[9px]"
            >
              {enviando ? "salvando…" : "Cadastrar"}
            </button>
            <span className="text-[12px] text-neutral-600">
              Ela entra na fila de hoje — não daqui a uma semana.
            </span>
          </div>
          </>
          )}
        </div>
      </aside>
    </div>
  );
}
