"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { AbasComercial } from "@/components/comercial/Abas";
import { Cabecalho, Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { EmpresaLinha, FiltroEmpresas, PaginaEmpresas } from "@/lib/tipos";

// Fase 1 do motor comercial, passo 2: procurar na base de prospecção e trazer
// para o CRM. O padrão é o foco da D11/D13: clínica de psicologia com equipe,
// com e-mail. Dez por vez (regra do serviço); pessoa física só uma, com
// confirmação (regras-prospeccao §4).

const MAX = 10;
const PADRAO: FiltroEmpresas = {
  termo: "psic",
  segmento: "clinica_especialidade",
  bairro: "",
  so_com_email: true,
  incluir_no_crm: true,
  offset: 0,
};

const SEGMENTOS: [string, string][] = [
  ["clinica_especialidade", "Clínica (com equipe)"],
  ["consultorio_isolado", "Consultório isolado"],
  ["todos", "Todos"],
];

const rotulo = "card-kicker mb-[6px] block text-neutral-400";

function Linha({
  e,
  marcada,
  bloqueada,
  onMarcar,
}: {
  e: EmpresaLinha;
  marcada: boolean;
  bloqueada: boolean;
  onMarcar: () => void;
}) {
  const noCrm = e.lead_id !== null;
  return (
    <tr className="border-t border-divider align-top">
      <td className="py-[10px] pr-3">
        <input
          type="checkbox"
          aria-label={`selecionar ${e.nome}`}
          checked={marcada}
          disabled={noCrm || (bloqueada && !marcada)}
          onChange={onMarcar}
        />
      </td>
      <td className="py-[10px] pr-3">
        <div className="text-[14px] text-text">{e.nome}</div>
        <div className="mt-[2px] flex flex-wrap gap-2 text-[11.5px] text-neutral-500">
          {e.cnes && <span className="tnum">CNES {e.cnes}</span>}
          {e.pessoa_fisica && (
            <span className="text-accent-300">
              pessoa física: revisão manual
            </span>
          )}
          {noCrm && (
            <Link
              href={`/comercial/leads/${e.lead_id}`}
              className="text-accent no-underline hover:underline"
            >
              no CRM →
            </Link>
          )}
        </div>
      </td>
      <td className="py-[10px] pr-3 text-[13px] text-muted">
        {e.bairro ?? "—"}
      </td>
      <td className="py-[10px] pr-3 text-[13px] text-muted">
        {e.emails.length ? e.emails.join(", ") : "—"}
      </td>
      <td className="tnum py-[10px] text-[13px] text-muted">
        {e.telefones[0] ?? "—"}
      </td>
    </tr>
  );
}

export default function Empresas() {
  const [filtro, setFiltro] = useState<FiltroEmpresas>(PADRAO);
  const [pagina, setPagina] = useState<PaginaEmpresas | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [marcadas, setMarcadas] = useState<Set<number>>(new Set());
  const [trazendo, setTrazendo] = useState(false);
  const [confirmarPf, setConfirmarPf] = useState<EmpresaLinha | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .empresas(filtro)
      .then((p) => {
        setPagina(p);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [filtro]);

  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const muda = (campo: keyof FiltroEmpresas, valor: string | boolean) => {
    setFiltro((f) => ({ ...f, [campo]: valor, offset: 0 }));
    setMarcadas(new Set());
  };

  const marcar = (id: number) =>
    setMarcadas((atual) => {
      const nova = new Set(atual);
      if (nova.has(id)) nova.delete(id);
      else if (nova.size < MAX) nova.add(id);
      return nova;
    });

  const trazer = async (ids: number[], confirmarPessoaFisica = false) => {
    setTrazendo(true);
    try {
      const r = await api.trazerEmpresas(ids, confirmarPessoaFisica);
      const pulados = Object.values(r.pulados);
      ok(
        `${plural(r.trazidos.length, "clínica trazida", "clínicas trazidas")} para o CRM` +
          (pulados.length
            ? `; ${plural(pulados.length, "ficou", "ficaram")} de fora (${[...new Set(pulados)].join("; ")})`
            : ""),
      );
      setMarcadas(new Set());
    } catch (e) {
      falhou("Não consegui trazer", e);
    } finally {
      setTrazendo(false);
    }
  };

  const clicarTrazer = () => {
    const ids = [...marcadas];
    const pf = pagina?.itens.find((e) => ids.includes(e.id) && e.pessoa_fisica);
    // Pessoa física só uma por vez, e com confirmação.
    if (pf && ids.length === 1) setConfirmarPf(pf);
    else void trazer(ids);
  };

  const mudouFiltro =
    JSON.stringify({ ...filtro, offset: 0 }) !== JSON.stringify(PADRAO);
  const total = pagina?.total ?? 0;
  const offset = filtro.offset ?? 0;

  return (
    <div className="max-w-[1100px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Comercial · Empresas</Cabecalho>
      <h1 className="m-0 mb-3 text-[clamp(32px,3.6vw,42px)]">CRM</h1>
      <p className="m-0 mb-6 max-w-[64ch] text-[15px] text-muted">
        A base de prospecção tem o que existe; o CRM tem quem você escolheu
        abordar. Marque até {MAX} e traga: cada uma vira um lead com a tarefa
        &ldquo;pesquisar&rdquo;. O e-mail da base só vira destinatário depois
        que o Pesquisador confirmar que a clínica o publica.
      </p>

      <AbasComercial />

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className={rotulo} htmlFor="emp-termo">
            Nome contém
          </label>
          <input
            id="emp-termo"
            className="input w-[160px]"
            value={filtro.termo ?? ""}
            onChange={(e) => muda("termo", e.target.value)}
          />
        </div>
        <div>
          <label className={rotulo} htmlFor="emp-segmento">
            Tipo
          </label>
          <select
            id="emp-segmento"
            className="input"
            value={filtro.segmento}
            onChange={(e) => muda("segmento", e.target.value)}
          >
            {SEGMENTOS.map(([v, r]) => (
              <option key={v} value={v}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={rotulo} htmlFor="emp-bairro">
            Bairro
          </label>
          <input
            id="emp-bairro"
            className="input w-[160px]"
            value={filtro.bairro ?? ""}
            placeholder="qualquer"
            onChange={(e) => muda("bairro", e.target.value)}
          />
        </div>
        <label className="flex items-center gap-2 pb-[9px] text-[13px] text-muted">
          <input
            type="checkbox"
            checked={filtro.so_com_email ?? true}
            onChange={(e) => muda("so_com_email", e.target.checked)}
          />
          só com e-mail
        </label>
        <label className="flex items-center gap-2 pb-[9px] text-[13px] text-muted">
          <input
            type="checkbox"
            checked={filtro.incluir_no_crm ?? true}
            onChange={(e) => muda("incluir_no_crm", e.target.checked)}
          />
          mostrar quem já está no CRM
        </label>
        {mudouFiltro && (
          <button
            type="button"
            className="btn btn-ghost pb-[9px] text-[12.5px]"
            onClick={() => {
              setFiltro(PADRAO);
              setMarcadas(new Set());
            }}
          >
            limpar
          </button>
        )}
        <button
          type="button"
          className="btn btn-primary ml-auto"
          disabled={marcadas.size === 0 || trazendo}
          onClick={clicarTrazer}
        >
          {trazendo
            ? "trazendo…"
            : marcadas.size
              ? `Trazer ${marcadas.size} para o CRM`
              : "Trazer para o CRM"}
        </button>
      </div>

      {erro && <Erro>Não consegui carregar a base: {erro}</Erro>}
      {!pagina && !erro && (
        <div className="text-[13px] text-muted">carregando…</div>
      )}

      {pagina && pagina.itens.length === 0 && (
        <Vazio titulo="Nenhuma clínica com esses filtros">
          Tente outro bairro, tire &ldquo;só com e-mail&rdquo; ou mude o tipo.
        </Vazio>
      )}

      {pagina && pagina.itens.length > 0 && (
        <div className="card overflow-x-auto">
          <div className="tnum mb-2 text-[12px] text-neutral-500">
            {plural(total, "estabelecimento", "estabelecimentos")} · mostrando{" "}
            {offset + 1}–{offset + pagina.itens.length}
            {marcadas.size > 0 && ` · ${marcadas.size} de ${MAX} marcadas`}
          </div>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="card-kicker text-neutral-500">
                <th className="w-[28px] pb-2" />
                <th className="pb-2 font-normal">Estabelecimento</th>
                <th className="pb-2 font-normal">Bairro</th>
                <th className="pb-2 font-normal">E-mail na base</th>
                <th className="pb-2 font-normal">Telefone</th>
              </tr>
            </thead>
            <tbody>
              {pagina.itens.map((e) => (
                <Linha
                  key={e.id}
                  e={e}
                  marcada={marcadas.has(e.id)}
                  bloqueada={marcadas.size >= MAX}
                  onMarcar={() => marcar(e.id)}
                />
              ))}
            </tbody>
          </table>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="btn btn-secondary text-[12.5px]"
              disabled={offset === 0}
              onClick={() =>
                setFiltro((f) => ({ ...f, offset: Math.max(0, offset - 50) }))
              }
            >
              ← anteriores
            </button>
            <button
              type="button"
              className="btn btn-secondary text-[12.5px]"
              disabled={offset + pagina.itens.length >= total}
              onClick={() => setFiltro((f) => ({ ...f, offset: offset + 50 }))}
            >
              próximas →
            </button>
          </div>
        </div>
      )}

      {confirmarPf && (
        <Dialogo
          titulo="Trazer pessoa física?"
          descricao={`"${confirmarPf.nome}" é pessoa física (consultório sem CNPJ, empresário individual ou MEI). A regra de prospecção pede revisão uma por uma: confira que o e-mail é claramente profissional antes de trazer.`}
          confirmar="trazer mesmo assim"
          onCancelar={() => setConfirmarPf(null)}
          onConfirmar={() => {
            const id = confirmarPf.id;
            setConfirmarPf(null);
            void trazer([id], true);
          }}
        />
      )}

      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </div>
  );
}
