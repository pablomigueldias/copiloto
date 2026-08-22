"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { Erro, Vazio, plural, quando } from "@/components/ui";
import { api } from "@/lib/api";
import { useAvisos } from "@/lib/avisos";
import type { ModuloResumo, Questao } from "@/lib/tipos";

import { GavetaQuestao } from "./GavetaQuestao";
import {
  AcoesDoModulo,
  DialogosDeOrganizar,
  NovoModulo,
  type Modo,
} from "./Organizar";

type Filtro = "todos" | "hoje" | "erradas" | "adiados";

const TRILHAS: { chave: string; titulo: string }[] = [
  { chave: "concurso", titulo: "Concurso" },
  { chave: "especializacao", titulo: "Especialização" },
];

function CardModulo({
  m,
  onAbrirTopico,
  onModo,
}: {
  m: ModuloResumo;
  onAbrirTopico: (id: string, nome: string) => void;
  onModo: (modo: Modo) => void;
}) {
  const [todos, setTodos] = useState(false);
  const topicos = todos ? m.topicos : m.topicos.slice(0, 5);
  const t = Math.max(m.questoes, 1);

  return (
    <article id={m.id} className="card elev-sm flex scroll-mt-6 flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <h3 className="m-0 text-[17px]">{m.nome}</h3>
        <span
          className={`tag flex-none ${m.hoje > 0 ? "tag-accent" : "tag-neutral"}`}
        >
          {m.hoje > 0 ? `${m.hoje} hoje` : quando(m.proxima_em)}
        </span>
      </div>

      <div className="flex h-[3px] gap-px overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--color-text)_8%,transparent)]">
        <span
          className="bg-accent"
          style={{ width: `${(m.dominadas / t) * 100}%` }}
        />
        <span
          className="bg-accent-800"
          style={{ width: `${(m.com_erro / t) * 100}%` }}
        />
      </div>

      <div className="tnum text-[12px] text-neutral-500">
        {plural(m.questoes, "questão", "questões")} ·{" "}
        {plural(m.topicos.length, "tópico", "tópicos")} · {m.dominadas} dominadas
        · {m.com_erro} com erro
      </div>

      {m.topicos.length === 0 && (
        <p className="m-0 text-[13px] text-neutral-500">
          Módulo vazio. Crie um tópico — questão não mora solta no módulo.
        </p>
      )}

      <div className="flex flex-col">
        {topicos.map((t) => (
          <div
            key={t.id}
            className="flex items-center gap-2 border-t border-[color-mix(in_srgb,var(--color-text)_7%,transparent)] py-[7px] text-[13.5px] first:border-t-0"
          >
            <button
              type="button"
              onClick={() => onAbrirTopico(t.id, t.nome)}
              className="min-w-0 flex-1 truncate text-left text-text hover:text-accent"
            >
              {t.nome}
            </button>
            <span className="tnum flex-none text-[12px] text-neutral-600">
              {t.questoes}
            </span>
            <Link
              href={`/revisar?topico=${t.id}`}
              className={`tnum w-[54px] flex-none text-right text-[12px] no-underline ${
                t.hoje > 0
                  ? "text-accent hover:underline"
                  : "text-neutral-600 hover:text-neutral-400"
              }`}
            >
              {t.hoje > 0 ? "hoje" : quando(t.proxima_em)}
            </Link>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-1">
        {m.topicos.length > 5 && (
          <button
            type="button"
            onClick={() => setTodos((v) => !v)}
            className="btn btn-ghost px-2 text-[12.5px]"
          >
            {todos
              ? "Mostrar menos"
              : `Ver os ${m.topicos.length} tópicos`}
          </button>
        )}
        {/* Módulo vazio não tem o que revisar — o botão só confundiria. */}
        {m.questoes > 0 && (
          <Link
            href={`/revisar?modulo=${m.id}${m.hoje > 0 ? "" : "&todas=1"}`}
            className="btn btn-ghost px-2 text-[12.5px]"
          >
            {m.hoje > 0 ? "Revisar o que vence" : "Fazer o módulo"}
          </Link>
        )}
        <span className="flex-1" />
        <AcoesDoModulo m={m} onModo={onModo} />
      </div>
    </article>
  );
}

function Modulos() {
  const params = useSearchParams();
  const [modulos, setModulos] = useState<ModuloResumo[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [busca, setBusca] = useState("");
  const [filtro, setFiltro] = useState<Filtro>("todos");

  const [topicoAberto, setTopicoAberto] = useState<{
    id: string;
    nome: string;
  } | null>(null);
  const [questoes, setQuestoes] = useState<Questao[] | null>(null);
  const [emFoco, setEmFoco] = useState<Questao | null>(null);
  const [verGabarito, setVerGabarito] = useState(false);
  const [modo, setModo] = useState<Modo | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = () =>
    api
      .modulos()
      .then(setModulos)
      .catch((e) => setErro(String(e.message ?? e)));

  useEffect(() => {
    void carregar();
  }, []);

  // ?questao=<id> — o link que a tela de revisão dá para escrever a explicação.
  useEffect(() => {
    const id = params.get("questao");
    if (id) api.questao(id).then(setEmFoco).catch(() => {});
  }, [params]);

  const abrirTopico = (id: string, nome: string) => {
    setTopicoAberto({ id, nome });
    setQuestoes(null);
    api
      .questoes({ topico_id: id, limite: 200 })
      .then((r) => setQuestoes(r.itens))
      .catch((e) => setErro(String(e.message ?? e)));
  };

  const filtrados = useMemo(() => {
    if (!modulos) return null;
    const alvo = busca.trim().toLowerCase();
    return modulos
      .map((m) => ({
        ...m,
        topicos: m.topicos.filter((t) => {
          if (alvo && !t.nome.toLowerCase().includes(alvo) && !m.nome.toLowerCase().includes(alvo))
            return false;
          if (filtro === "hoje") return t.hoje > 0;
          if (filtro === "erradas") return t.com_erro > 0;
          return true;
        }),
      }))
      .filter((m) => m.topicos.length > 0 || (!alvo && filtro === "todos"));
  }, [modulos, busca, filtro]);

  return (
    <div className="max-w-[1180px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">Módulos</h1>
      <p className="m-0 mb-6 max-w-[62ch] text-[15px] text-muted">
        Toda questão nasce dentro de um tópico, e todo tópico dentro de um
        módulo. É esse par que o agendamento usa quando devolve a questão para
        você — em sete dias se acertar, em dois se errar.
      </p>

      {erro && <Erro>{erro}</Erro>}

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <input
          className="input max-w-[280px] flex-1"
          type="search"
          placeholder="Buscar módulo ou tópico"
          aria-label="Buscar módulo ou tópico"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
        <div className="flex gap-1 rounded-[8px] border border-divider p-[3px]">
          {(
            [
              ["todos", "Todos"],
              ["hoje", "Vencendo hoje"],
              ["erradas", "Com erradas"],
            ] as const
          ).map(([k, r]) => (
            <button
              key={k}
              type="button"
              onClick={() => setFiltro(k)}
              className={`rounded-[6px] px-[10px] py-[5px] text-[12.5px] transition-colors ${
                filtro === k
                  ? "bg-[color-mix(in_srgb,var(--color-accent)_14%,transparent)] text-accent-200"
                  : "text-neutral-400 hover:text-text"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          <NovoModulo
            onErro={falhou}
            onCriado={(_id, nome) => {
              ok(`Módulo "${nome}" criado — agora crie um tópico nele`);
              void carregar();
            }}
          />
          <Link href="/formatos" className="btn btn-primary">
            Nova questão
          </Link>
        </div>
      </div>

      {!modulos && (
        <p className="text-[13px] text-neutral-500">carregando módulos…</p>
      )}

      {modulos?.length === 0 && (
        <Vazio titulo="Nenhum módulo cadastrado">
          Comece por <strong className="font-medium text-text">Novo módulo</strong>{" "}
          aqui em cima — ou traga um acervo pronto com{" "}
          <code className="font-mono text-[13px] text-accent-300">
            python scripts/importar_questoes.py data/estudo/logica-proposicional.json
          </code>
          .
        </Vazio>
      )}

      {TRILHAS.map(({ chave, titulo }) => {
        const doGrupo = filtrados?.filter((m) => m.trilha === chave) ?? [];
        if (!doGrupo.length) return null;
        const total = doGrupo.reduce((s, m) => s + m.questoes, 0);
        return (
          <section key={chave} className="mb-9">
            <div className="mb-4 flex items-baseline gap-3">
              <h2 className="m-0 text-[19px]">{titulo}</h2>
              <span className="h-px flex-1 bg-divider" />
              <span className="tnum flex-none text-[12px] text-neutral-500">
                {plural(doGrupo.length, "módulo", "módulos")} ·{" "}
                {plural(total, "questão", "questões")}
              </span>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {doGrupo.map((m) => (
                <CardModulo
                  key={m.id}
                  m={m}
                  onAbrirTopico={abrirTopico}
                  onModo={setModo}
                />
              ))}
            </div>
          </section>
        );
      })}

      {topicoAberto && (
        <section className="mt-8">
          <div className="mb-4 flex flex-wrap items-baseline gap-3">
            <h2 className="m-0 text-[19px]">{topicoAberto.nome}</h2>
            <Link
              href={`/revisar?topico=${topicoAberto.id}&todas=1`}
              className="btn btn-primary flex-none py-[5px] text-[12.5px]"
            >
              Fazer as questões
            </Link>
            <Link
              href={`/revisar?topico=${topicoAberto.id}`}
              className="btn btn-secondary flex-none py-[5px] text-[12.5px]"
            >
              Só o que vence hoje
            </Link>
            <span className="h-px flex-1 bg-divider" />
            {/* O acervo é onde eu confiro o gabarito; a lista também é de onde
                eu começo a responder. Deixá-lo à mostra por padrão estragaria a
                questão antes de eu tentar. */}
            <label className="flex flex-none cursor-pointer items-center gap-2 text-[12.5px] text-neutral-400">
              <input
                type="checkbox"
                checked={verGabarito}
                onChange={(e) => setVerGabarito(e.target.checked)}
              />
              mostrar gabarito
            </label>
            <button
              type="button"
              onClick={() =>
                setModo({
                  tipo: "renomear-topico",
                  id: topicoAberto.id,
                  nome: topicoAberto.nome,
                })
              }
              className="btn btn-ghost flex-none py-1 text-[12.5px]"
            >
              renomear
            </button>
            <button
              type="button"
              onClick={() =>
                setModo({
                  tipo: "apagar-topico",
                  id: topicoAberto.id,
                  nome: topicoAberto.nome,
                  questoes: questoes?.length ?? 0,
                })
              }
              className="btn btn-ghost flex-none py-1 text-[12.5px]"
            >
              apagar
            </button>
            <button
              type="button"
              onClick={() => setTopicoAberto(null)}
              className="btn btn-ghost flex-none py-1 text-[12.5px]"
            >
              fechar
            </button>
          </div>
          {!questoes ? (
            <p className="text-[13px] text-neutral-500">carregando questões…</p>
          ) : questoes.length === 0 ? (
            <Vazio
              titulo="Tópico sem questões"
              acao={{ href: "/formatos", rotulo: "Cadastrar a primeira" }}
            >
              Escolha o formato mais próximo do conteúdo e o resto da tela se
              resolve.
            </Vazio>
          ) : (
            <div className="overflow-x-auto">
              <table className="table min-w-[760px]">
                <thead>
                  <tr>
                    {verGabarito && <th className="w-[60px]">Gab.</th>}
                    <th>Enunciado</th>
                    <th className="w-[110px]">Formato</th>
                    <th className="w-[110px]">Volta</th>
                    <th className="w-[100px]">Acerto</th>
                    <th className="w-[150px]" />
                  </tr>
                </thead>
                <tbody>
                  {questoes.map((q) => (
                    <tr key={q.id}>
                      {verGabarito && (
                        <td className="tnum text-accent">{q.gabarito}</td>
                      )}
                      <td className="max-w-[420px]">
                        <div className="line-clamp-2 text-[13.5px]">
                          {q.enunciado}
                        </div>
                        {!q.explicacao && (
                          <span className="mt-1 inline-block text-[11px] text-neutral-600">
                            sem explicação
                          </span>
                        )}
                      </td>
                      <td className="text-[12.5px] text-neutral-400">
                        {q.formato.replace("_", " ")}
                      </td>
                      <td className="tnum text-[12.5px] text-neutral-400">
                        {quando(q.agenda?.proxima_em)}
                      </td>
                      <td className="tnum text-[12.5px] text-neutral-400">
                        {q.agenda && q.agenda.total_acertos + q.agenda.total_erros > 0
                          ? `${q.agenda.total_acertos}/${q.agenda.total_acertos + q.agenda.total_erros}`
                          : "—"}
                      </td>
                      <td>
                        <div className="flex gap-1">
                          <Link
                            href={`/revisar?questao=${q.id}`}
                            className="btn btn-secondary px-2 py-1 text-[12.5px]"
                          >
                            responder
                          </Link>
                          <button
                            type="button"
                            onClick={() => setEmFoco(q)}
                            className="btn btn-ghost px-2 py-1 text-[12.5px]"
                          >
                            abrir
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <DialogosDeOrganizar
        modo={modo}
        onFechar={() => setModo(null)}
        onFeito={() => {
          setTopicoAberto(null);
          void carregar();
        }}
        onOk={ok}
        onErro={falhou}
      />

      {aviso && <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />}

      {emFoco && (
        <GavetaQuestao
          key={emFoco.id}
          questao={emFoco}
          onFechar={() => setEmFoco(null)}
          onSalvo={(q) => {
            setEmFoco(q);
            setQuestoes((atual) =>
              atual ? atual.map((x) => (x.id === q.id ? q : x)) : atual,
            );
            carregar();
          }}
        />
      )}
    </div>
  );
}

export default function Page() {
  return (
    <Suspense fallback={<div className="p-8 text-[13px] text-neutral-500">…</div>}>
      <Modulos />
    </Suspense>
  );
}
