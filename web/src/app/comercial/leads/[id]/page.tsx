"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Aviso } from "@/components/Dialogo";
import { AbasComercial } from "@/components/comercial/Abas";
import { Cabecalho, Erro, quando } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import {
  CartaoEmail,
  Ficha,
  Fonte,
  Pesquisar,
  dataHora,
} from "@/components/comercial/Prospeccao";
import type { LeadDetalhe } from "@/lib/tipos";

// O lead e a ficha do Pesquisador (Fase 1, passo 3). Cada fato mostra a página
// de onde veio: é o que deixa conferir antes de escrever para a clínica.

const ROTULO: Record<string, string> = {
  email_frio: "e-mail 1 enviado",
  lembrete_frio: "lembrete enviado",
};

export default function LeadPagina() {
  const { id } = useParams<{ id: string }>();
  const [lead, setLead] = useState<LeadDetalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
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

  const ficha = lead?.interacoes.find((i) => i.tipo === "ficha")?.dados ?? null;
  const abertas = lead?.tarefas.filter((t) => !t.feita_em) ?? [];

  return (
    <div className="max-w-[1100px] px-[clamp(24px,4vw,56px)] pb-14 pt-[34px]">
      <Cabecalho>Comercial · Negócio</Cabecalho>
      {erro && <Erro>Não consegui carregar o lead: {erro}</Erro>}
      {lead && (
        <>
          <h1 className="m-0 mb-2 text-[clamp(28px,3.2vw,38px)]">
            {lead.nome}
          </h1>
          <p className="m-0 mb-6 text-[14px] text-muted">
            {lead.estagio} · {lead.proxima_acao ?? "pesquisar"} ·{" "}
            <Link href={`/comercial/negocios?abrir=${lead.id}`}>
              ficha no CRM (empresa, contatos, atividades)
            </Link>
          </p>
          <AbasComercial />

          <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.2fr_1fr]">
            <div className="flex flex-col gap-5">
              <Pesquisar lead={lead} onLead={setLead} ok={ok} falhou={falhou} />
              <CartaoEmail
                lead={lead}
                onLead={setLead}
                ok={ok}
                falhou={falhou}
              />
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
                        {ROTULO[i.tipo ?? ""] ?? i.tipo ?? i.canal} ·{" "}
                        {dataHora(i.criado_em)}
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
