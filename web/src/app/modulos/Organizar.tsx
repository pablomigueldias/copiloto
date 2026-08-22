"use client";

import { useState } from "react";

import { Dialogo } from "@/components/Dialogo";
import { api, ApiErro } from "@/lib/api";
import type { ModuloResumo } from "@/lib/tipos";

const TRILHAS: [string, string, string][] = [
  ["concurso", "Concurso", "a prova que tem data"],
  ["especializacao", "Especialização", "o assunto que tem carreira"],
];

const campo = "input";
const rotulo = "card-kicker mb-[6px] block text-neutral-400";

/** Novo módulo — nome e a trilha em que ele aparece na sidebar. */
export function NovoModulo({
  onCriado,
  onErro,
}: {
  onCriado: (id: string, nome: string) => void;
  onErro: (msg: string, e: unknown) => void;
}) {
  const [aberto, setAberto] = useState(false);
  const [nome, setNome] = useState("");
  const [trilha, setTrilha] = useState("concurso");
  const [enviando, setEnviando] = useState(false);

  const criar = async () => {
    setEnviando(true);
    try {
      const m = await api.criarModulo({ nome: nome.trim(), trilha });
      setAberto(false);
      setNome("");
      onCriado(m.id, m.nome);
    } catch (e) {
      onErro(
        e instanceof ApiErro && e.status === 409
          ? "Esse módulo já existe"
          : "Não consegui criar o módulo",
        e instanceof ApiErro && e.status === 409 ? undefined : e,
      );
    } finally {
      setEnviando(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setAberto(true)}
        className="btn btn-secondary"
      >
        Novo módulo
      </button>
      {aberto && (
        <Dialogo
          titulo="Novo módulo"
          descricao="Uma matéria — Estatística, Python, Direito Administrativo. Ela nasce vazia; o próximo passo é criar um tópico dentro."
          confirmar={enviando ? "criando…" : "criar"}
          desabilitado={enviando || !nome.trim()}
          onCancelar={() => setAberto(false)}
          onConfirmar={criar}
        >
          <label className={rotulo} htmlFor="modulo-nome">
            Nome
          </label>
          <input
            id="modulo-nome"
            className={`${campo} mb-3`}
            value={nome}
            autoFocus
            onChange={(e) => setNome(e.target.value)}
            placeholder="Estatística e probabilidade"
          />
          <span className={rotulo}>Trilha</span>
          <div className="mb-3 flex flex-col gap-1">
            {TRILHAS.map(([k, r, porque]) => (
              <label
                key={k}
                className="flex cursor-pointer items-baseline gap-2 text-[13.5px]"
              >
                <input
                  type="radio"
                  name="trilha"
                  checked={trilha === k}
                  onChange={() => setTrilha(k)}
                />
                {r}
                <span className="text-[12px] text-neutral-600">— {porque}</span>
              </label>
            ))}
          </div>
        </Dialogo>
      )}
    </>
  );
}

type Modo =
  | { tipo: "topico"; moduloId: string; moduloNome: string }
  | { tipo: "renomear-modulo"; id: string; nome: string }
  | { tipo: "renomear-topico"; id: string; nome: string }
  | { tipo: "apagar-modulo"; id: string; nome: string; questoes: number }
  | { tipo: "apagar-topico"; id: string; nome: string; questoes: number };

/**
 * Os diálogos de organizar — criar tópico, renomear e apagar.
 *
 * Apagar recusa por padrão quando há questões dentro; a tela reenvia com
 * `forcar` só depois de dizer, com o número na mão, que o histórico de
 * respostas vai junto. Meses de repetição espaçada são a única coisa aqui que
 * não se refaz.
 */
export function DialogosDeOrganizar({
  modo,
  onFechar,
  onFeito,
  onErro,
  onOk,
}: {
  modo: Modo | null;
  onFechar: () => void;
  onFeito: () => void;
  onErro: (msg: string, e: unknown) => void;
  onOk: (msg: string) => void;
}) {
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);

  if (!modo) return null;

  const roda = async (fn: () => Promise<unknown>, sucesso: string, falha: string) => {
    setEnviando(true);
    try {
      await fn();
      onOk(sucesso);
      setNome("");
      onFechar();
      onFeito();
    } catch (e) {
      onErro(
        e instanceof ApiErro && e.status === 409 ? (e.message ?? falha) : falha,
        e instanceof ApiErro && e.status === 409 ? undefined : e,
      );
    } finally {
      setEnviando(false);
    }
  };

  if (modo.tipo === "topico") {
    return (
      <Dialogo
        titulo={`Novo tópico em ${modo.moduloNome}`}
        descricao="É o par módulo+tópico que a revisão mostra no topo, e é por ele que o agendamento devolve a questão."
        confirmar={enviando ? "criando…" : "criar"}
        desabilitado={enviando || !nome.trim()}
        onCancelar={onFechar}
        onConfirmar={() =>
          roda(
            () => api.criarTopico(modo.moduloId, { nome: nome.trim() }),
            `Tópico "${nome.trim()}" criado`,
            "Não consegui criar o tópico",
          )
        }
      >
        <label className={rotulo} htmlFor="topico-nome">
          Nome
        </label>
        <input
          id="topico-nome"
          className={`${campo} mb-3`}
          value={nome}
          autoFocus
          onChange={(e) => setNome(e.target.value)}
          placeholder="Probabilidade condicional e Bayes"
        />
      </Dialogo>
    );
  }

  if (modo.tipo === "renomear-modulo" || modo.tipo === "renomear-topico") {
    const ehModulo = modo.tipo === "renomear-modulo";
    return (
      <Dialogo
        titulo={ehModulo ? "Renomear o módulo" : "Renomear o tópico"}
        confirmar={enviando ? "salvando…" : "salvar"}
        desabilitado={enviando || !nome.trim()}
        onCancelar={onFechar}
        onConfirmar={() =>
          roda(
            () =>
              ehModulo
                ? api.editarModulo(modo.id, { nome: nome.trim() })
                : api.editarTopico(modo.id, { nome: nome.trim() }),
            "Renomeado",
            "Não consegui renomear",
          )
        }
      >
        <input
          className={`${campo} mb-3`}
          value={nome || modo.nome}
          autoFocus
          onChange={(e) => setNome(e.target.value)}
          aria-label="novo nome"
        />
      </Dialogo>
    );
  }

  const ehModulo = modo.tipo === "apagar-modulo";
  const n = modo.questoes;
  return (
    <Dialogo
      titulo={`Apagar ${ehModulo ? "o módulo" : "o tópico"} "${modo.nome}"?`}
      descricao={
        n > 0
          ? `Vão junto ${n} ${n === 1 ? "questão" : "questões"} e todo o histórico de respostas delas — quantas vezes você acertou, quando, e a data em que cada uma voltaria. Isso não se refaz.`
          : "Está vazio — nada de histórico se perde."
      }
      confirmar={enviando ? "apagando…" : n > 0 ? `apagar assim mesmo` : "apagar"}
      perigo
      desabilitado={enviando}
      onCancelar={onFechar}
      onConfirmar={() =>
        roda(
          () =>
            ehModulo
              ? api.apagarModulo(modo.id, n > 0)
              : api.apagarTopico(modo.id, n > 0),
          n > 0 ? `Apagado — ${n} questão(ões) foram junto` : "Apagado",
          "Não consegui apagar",
        )
      }
    />
  );
}

export type { Modo };

/** Os botões de organizar que ficam no rodapé do card do módulo. */
export function AcoesDoModulo({
  m,
  onModo,
}: {
  m: ModuloResumo;
  onModo: (modo: Modo) => void;
}) {
  return (
    <>
      <button
        type="button"
        onClick={() =>
          onModo({ tipo: "topico", moduloId: m.id, moduloNome: m.nome })
        }
        className="btn btn-ghost px-2 text-[12.5px]"
      >
        + tópico
      </button>
      <button
        type="button"
        onClick={() =>
          onModo({ tipo: "renomear-modulo", id: m.id, nome: m.nome })
        }
        className="btn btn-ghost px-2 text-[12.5px]"
      >
        renomear
      </button>
      <button
        type="button"
        onClick={() =>
          onModo({
            tipo: "apagar-modulo",
            id: m.id,
            nome: m.nome,
            questoes: m.questoes,
          })
        }
        className="btn btn-ghost px-2 text-[12.5px]"
      >
        apagar
      </button>
    </>
  );
}
