"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { Cabecalho, Erro, Vazio } from "@/components/ui";
import { api } from "@/lib/api";
import { useAvisos } from "@/lib/avisos";
import type { Acao } from "@/lib/tipos";

const STATUS = ["pendente", "aprovada", "editada", "rejeitada"] as const;

/** "há 3 min", "há 2 h" — o que interessa é o tempo parado, não o relógio. */
function haQuanto(iso: string): string {
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "agora";
  if (s < 3600) return `há ${Math.floor(s / 60)} min`;
  if (s < 86400) return `há ${Math.floor(s / 3600)} h`;
  return `há ${Math.floor(s / 86400)} d`;
}

function Cartao({
  acao,
  onDecidida,
  onSujo,
  onErro,
}: {
  acao: Acao;
  onDecidida: (msg: string) => void;
  onSujo: (sujo: boolean) => void;
  onErro: (msg: string, e: unknown) => void;
}) {
  const [texto, setTexto] = useState(acao.texto_gerado ?? "");
  const [enviando, setEnviando] = useState(false);
  const [perguntando, setPerguntando] = useState(false);

  const pendente = acao.status === "pendente";
  const editado = texto !== (acao.texto_gerado ?? "");

  const decidir = async (
    decisao: "aprovar" | "rejeitar",
    motivo?: string,
  ) => {
    setEnviando(true);
    try {
      await api.decidir(acao.id, {
        decisao,
        ...(decisao === "aprovar" ? { texto_final: texto } : { motivo }),
      });
      onSujo(false);
      onDecidida(
        decisao === "aprovar"
          ? editado
            ? "Aprovado com a sua edição — virou par de preferência"
            : "Aprovado — virou exemplo de estilo"
          : "Rejeitado",
      );
    } catch (e) {
      onErro("Não consegui registrar a decisão", e);
    } finally {
      setEnviando(false);
    }
  };

  const avisos = acao.payload?.avisos ?? [];
  const rejeitados = acao.payload?.rejeitados ?? [];
  const vagaId = acao.payload?.vaga_id;

  return (
    <article className="card elev-sm">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <span className="text-[15px]">{acao.titulo}</span>
        <span className="card-kicker">
          {acao.agente} · {acao.tipo}
        </span>
        <span className="tnum ml-auto text-[11.5px] text-neutral-600">
          {haQuanto(acao.criada_em)}
        </span>
      </div>

      {acao.contexto && (
        <p className="m-0 mb-2 text-[13px] text-neutral-500">{acao.contexto}</p>
      )}

      {pendente ? (
        <textarea
          className="input min-h-[190px] resize-y font-mono text-[13px] leading-[1.6]"
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            onSujo(true);
          }}
          onBlur={() => onSujo(editado)}
        />
      ) : (
        <pre className="m-0 overflow-x-auto whitespace-pre-wrap rounded-[8px] border border-divider bg-[color-mix(in_srgb,black_20%,transparent)] p-3 font-mono text-[12.5px] leading-[1.6] text-muted">
          {acao.texto_final ?? acao.texto_gerado}
        </pre>
      )}

      {avisos.map((a, i) => (
        <div key={i} className="mt-2 text-[12.5px] text-accent-300">
          ⚠ {a}
        </div>
      ))}
      {rejeitados.length > 0 && (
        <div className="mt-2 text-[12.5px] text-accent-300">
          {rejeitados.length} trecho(s) removidos pela anti-alucinação
        </div>
      )}
      {acao.motivo && (
        <div className="mt-2 text-[12.5px] text-neutral-500">
          motivo: {acao.motivo}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {pendente && (
          <>
            <button
              type="button"
              disabled={enviando}
              onClick={() => decidir("aprovar")}
              className="btn btn-primary"
            >
              {enviando ? "…" : editado ? "aprovar com a edição" : "aprovar"}
            </button>
            <button
              type="button"
              disabled={enviando}
              onClick={() => setPerguntando(true)}
              className="btn btn-secondary"
            >
              rejeitar
            </button>
          </>
        )}
        {/* Currículo se julga vendo o PDF: é o mesmo arquivo que o ATS lê. */}
        {vagaId && (
          <a
            href={api.urlCurriculoPdf(vagaId)}
            target="_blank"
            rel="noopener"
            className="btn btn-ghost"
          >
            ver PDF
          </a>
        )}
        {editado && pendente && (
          <span className="ml-auto text-[12px] text-accent-300">
            editado — aprovar assim grava o par de treino
          </span>
        )}
      </div>

      {perguntando && (
        <Dialogo
          titulo="Por que rejeitar?"
          descricao="O motivo vira sinal de treino — vale escrever o que ficou errado."
          confirmar="rejeitar"
          perigo
          multilinha
          placeholder="inventou uma tecnologia que eu não tenho; tom errado; …"
          onCancelar={() => setPerguntando(false)}
          onConfirmar={(motivo) => {
            setPerguntando(false);
            void decidir("rejeitar", motivo);
          }}
        />
      )}
    </article>
  );
}

export default function Fila() {
  const [status, setStatus] = useState<string>("pendente");
  const [dados, setDados] = useState<{
    status: string;
    itens: Acao[];
    porStatus: Record<string, number>;
  } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  // Cartão sendo editado congela o refresco. O defeito que isto evita é o do
  // painel antigo: repintar a cada 15 s substituía o textarea inteiro e apagava
  // o que eu tinha acabado de escrever, sem aviso.
  const sujos = useRef(new Set<string>());
  // `pausado` é escrito pelo handler do cartão, nunca pelo efeito: um `ref` não
  // repinta a tela, e um `setState` no corpo do efeito dispara render em
  // cascata a cada tique do timer.
  const [pausado, setPausado] = useState(false);

  const itens = dados?.status === status ? dados.itens : null;
  const porStatus = dados?.porStatus ?? {};

  // Sem `async`: todo `setState` mora dentro de um `.then`. Chamada de função
  // `async` começa a executar de forma síncrona até o primeiro `await`, e é por
  // isso que o lint do React 19 a trata como escrita síncrona dentro do efeito.
  const carregar = useCallback(
    (forcar = false): Promise<void> => {
      // Cartão sujo não recarrega. O defeito que isto evita é o do painel
      // antigo: repintar a cada 15 s trocava o textarea e apagava o rascunho.
      if (!forcar && sujos.current.size > 0) return Promise.resolve();
      return api
        .filaAprovacao(status)
        .then((r) => setDados({ status, itens: r.itens, porStatus: r.por_status }))
        .catch((e: Error) => setErro(String(e.message ?? e)));
    },
    [status],
  );

  useEffect(() => {
    void carregar();
    const t = setInterval(() => void carregar(), 15000);
    return () => clearInterval(t);
  }, [carregar]);

  const marcarSujo = (id: string, sujo: boolean) => {
    if (sujo) sujos.current.add(id);
    else sujos.current.delete(id);
    setPausado(sujos.current.size > 0);
  };

  return (
    <div className="max-w-[1000px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Fila de aprovação</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">
        O que espera decisão
      </h1>
      <p className="m-0 mb-6 max-w-[62ch] text-[15px] text-muted">
        O agente observa e prepara sozinho; executar é decisão minha. O que eu
        aprovo vira exemplo de estilo; o que eu <strong>edito antes</strong> de
        aprovar vira par de preferência para o fine-tune — por isso o texto é
        editável aqui, e não só legível.
      </p>

      {erro && <Erro>{erro}</Erro>}

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="flex w-fit gap-1 rounded-[8px] border border-divider p-[3px]">
          {STATUS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatus(s)}
              className={`rounded-[6px] px-[11px] py-[5px] text-[12.5px] capitalize transition-colors ${
                status === s
                  ? "bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent-200"
                  : "text-neutral-400 hover:text-text"
              }`}
            >
              {s}
              {porStatus[s] ? (
                <span className="tnum ml-[6px] text-neutral-600">
                  {porStatus[s]}
                </span>
              ) : null}
            </button>
          ))}
        </div>
        {pausado && (
          <div className="flex items-center gap-2 text-[12.5px] text-accent-300">
            refresco pausado — você está editando
            <button
              type="button"
              onClick={() => {
                sujos.current.clear();
                setPausado(false);
                void carregar(true);
              }}
              className="btn btn-secondary py-[4px] text-[12px]"
            >
              atualizar mesmo assim
            </button>
          </div>
        )}
      </div>

      {!itens && <p className="text-[13px] text-neutral-500">carregando…</p>}

      {itens?.length === 0 && (
        <Vazio titulo="Nada esperando decisão">
          Sem ações com status <em>{status}</em>.
        </Vazio>
      )}

      <div className="flex flex-col gap-3">
        {itens?.map((a) => (
          <Cartao
            key={a.id}
            acao={a}
            onSujo={(sujo) => marcarSujo(a.id, sujo)}
            onErro={falhou}
            onDecidida={(msg) => {
              ok(msg);
              sujos.current.delete(a.id);
              setPausado(sujos.current.size > 0);
              void carregar(true);
            }}
          />
        ))}
      </div>

      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </div>
  );
}
