"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { AbasComercial } from "@/components/comercial/Abas";
import { Cabecalho, Erro, quando } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { FatoFicha, FichaDados, LeadDetalhe } from "@/lib/tipos";

// O lead e a ficha do Pesquisador (Fase 1, passo 3). Cada fato mostra a página
// de onde veio: é o que deixa conferir antes de escrever para a clínica.

/** "27/09, 14:05": a linha do tempo é passado, e com hora. */
function dataHora(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function Fonte({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-2 text-[11.5px] text-neutral-500 hover:text-accent"
    >
      fonte ↗
    </a>
  );
}

function Fato({
  rotulo,
  fato,
  formato,
}: {
  rotulo: string;
  fato: FatoFicha | null;
  formato?: (v: FatoFicha["valor"]) => string;
}) {
  return (
    <div className="flex flex-col gap-[2px] border-t border-divider py-[9px] first:border-t-0">
      <span className="card-kicker text-neutral-500">{rotulo}</span>
      {fato ? (
        <span className="text-[14px] text-text">
          {formato ? formato(fato.valor) : String(fato.valor)}
          <Fonte url={fato.fonte} />
        </span>
      ) : (
        <span className="text-[13.5px] text-neutral-500">
          não achei no site
        </span>
      )}
    </div>
  );
}

const PAROU: Record<string, string> = {
  completo: "parou porque achou tudo",
  teto: "parou no teto de páginas sem achar tudo",
  "acabaram as páginas": "leu o site inteiro",
};

function Ficha({ d }: { d: FichaDados }) {
  const js = d.com_javascript?.length ?? 0;
  return (
    <div className="card">
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className="m-0 text-[17px]">Ficha</h2>
        <span className="text-[12px] text-neutral-500">
          {d.paginas.length} página(s) lida(s) de {d.site}
          {d.parou_porque && PAROU[d.parou_porque]
            ? ` · ${PAROU[d.parou_porque]}`
            : ""}
          {js ? ` · ${js} com JavaScript` : ""}
        </span>
      </div>
      <Fato rotulo="O que a clínica faz" fato={d.o_que_faz} />
      <Fato rotulo="Gancho para o e-mail" fato={d.gancho} />
      <Fato rotulo="Psicólogos com CRP no site" fato={d.psicologos_crp} />
      <Fato
        rotulo="Agendamento online"
        fato={d.agendamento_online}
        formato={(v) => `sim (“${v}”)`}
      />
      <Fato
        rotulo="WhatsApp publicado"
        fato={d.whatsapp}
        formato={(v) => `sim: ${v}`}
      />
      <div className="flex flex-col gap-[2px] border-t border-divider py-[9px]">
        <span className="card-kicker text-neutral-500">E-mails publicados</span>
        {d.emails.length ? (
          d.emails.map((e) => (
            <span key={String(e.valor)} className="text-[14px] text-text">
              {String(e.valor)}
              <Fonte url={e.fonte} />
            </span>
          ))
        ) : (
          <span className="text-[13.5px] text-neutral-500">nenhum</span>
        )}
      </div>
    </div>
  );
}

export default function LeadPagina() {
  const { id } = useParams<{ id: string }>();
  const [lead, setLead] = useState<LeadDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [site, setSite] = useState("");
  const [pesquisando, setPesquisando] = useState(false);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .lead(Number(id))
      .then((l) => {
        setLead(l);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [id]);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const pesquisar = async () => {
    if (!lead) return;
    setPesquisando(true);
    try {
      const r = await api.pesquisarLead(lead.id, site.trim() || undefined);
      setLead(r.lead);
      if (r.status === "ok")
        ok(
          r.email_confirmado
            ? "Ficha pronta: e-mail confirmado no site"
            : "Ficha pronta, mas nenhum e-mail confirmado no site",
        );
      else falhou(r.mensagem);
    } catch (e) {
      falhou("A pesquisa falhou", e);
    } finally {
      setPesquisando(false);
    }
  };

  const ficha = lead?.interacoes.find((i) => i.tipo === "ficha")?.dados ?? null;
  const abertas = lead?.tarefas.filter((t) => !t.feita_em) ?? [];

  return (
    <div className="max-w-[1100px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Comercial · Lead</Cabecalho>
      {erro && <Erro>Não consegui carregar o lead: {erro}</Erro>}
      {lead && (
        <>
          <h1 className="m-0 mb-2 text-[clamp(28px,3.2vw,38px)]">
            {lead.nome}
          </h1>
          <p className="m-0 mb-6 text-[14px] text-muted">
            {lead.estagio} · {lead.proxima_acao ?? "pesquisar"}
          </p>
          <AbasComercial />

          <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.2fr_1fr]">
            <div className="flex flex-col gap-5">
              <div className="card">
                <h2 className="m-0 mb-3 text-[17px]">Pesquisar</h2>
                <p className="m-0 mb-3 text-[13.5px] text-muted">
                  Lê o site público da clínica página por página (contato,
                  equipe e agendamento primeiro) e para assim que acha e-mail,
                  WhatsApp, agendamento e equipe, ou em 15 páginas. Página
                  montada por JavaScript é aberta num navegador. Respeita o
                  robots.txt. Sem endereço, usa o domínio do e-mail, se não for
                  de provedor gratuito.
                </p>
                <div className="flex flex-wrap gap-2">
                  <input
                    className="input min-w-[240px] flex-1"
                    placeholder={
                      lead.site ?? "site da clínica (ex.: clinicaaurora.com.br)"
                    }
                    value={site}
                    onChange={(e) => setSite(e.target.value)}
                    aria-label="site da clínica"
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={pesquisando}
                    onClick={pesquisar}
                  >
                    {pesquisando
                      ? "lendo o site…"
                      : ficha
                        ? "Pesquisar de novo"
                        : "Pesquisar"}
                  </button>
                </div>
              </div>
              {ficha ? <Ficha d={ficha} /> : null}
            </div>

            <div className="flex flex-col gap-5">
              <div className="card">
                <h2 className="m-0 mb-3 text-[17px]">Contato</h2>
                <div className="text-[14px]">
                  {lead.email ?? "sem e-mail"}
                  {lead.email && (
                    <span
                      className={`ml-2 text-[12px] ${lead.email_confirmado ? "text-accent" : "text-accent-300"}`}
                    >
                      {lead.email_confirmado
                        ? "confirmado no site"
                        : "não confirmado: não enviar"}
                    </span>
                  )}
                  {lead.email_fonte && <Fonte url={lead.email_fonte} />}
                </div>
                {lead.telefone && (
                  <div className="tnum mt-1 text-[13px] text-muted">
                    {lead.telefone}
                  </div>
                )}
                {lead.site && (
                  <a
                    href={lead.site}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-1 block text-[13px] text-muted hover:text-accent"
                  >
                    {lead.site}
                  </a>
                )}
              </div>
              <div className="card">
                <h2 className="m-0 mb-3 text-[17px]">Tarefas abertas</h2>
                {abertas.length ? (
                  abertas.map((t) => (
                    <div key={t.id} className="text-[13.5px] text-text">
                      {t.tipo.replace("_", " ")}{" "}
                      <span className="tnum text-neutral-500">
                        · {quando(t.vence_em)}
                      </span>
                    </div>
                  ))
                ) : (
                  <span className="text-[13.5px] text-neutral-500">
                    nenhuma
                  </span>
                )}
              </div>
              <div className="card">
                <h2 className="m-0 mb-3 text-[17px]">Linha do tempo</h2>
                {lead.interacoes.length ? (
                  lead.interacoes.map((i) => (
                    <div
                      key={i.id}
                      className="border-t border-divider py-2 first:border-t-0"
                    >
                      <div className="card-kicker text-neutral-500">
                        {i.tipo ?? i.canal} · {dataHora(i.criado_em)}
                      </div>
                      <div className="whitespace-pre-line text-[13px] text-muted">
                        {i.texto}
                      </div>
                    </div>
                  ))
                ) : (
                  <span className="text-[13.5px] text-neutral-500">
                    nada ainda
                  </span>
                )}
              </div>
            </div>
          </div>
        </>
      )}
      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </div>
  );
}
