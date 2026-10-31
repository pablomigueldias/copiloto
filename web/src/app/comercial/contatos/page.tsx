"use client";

import { useCallback, useEffect, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { FichaCrm } from "@/components/comercial/FichaCrm";
import { FormCrm } from "@/components/comercial/FormCrm";
import {
  BarraLista,
  Celula,
  TelaCrm,
  td,
  th,
  useAtrasado,
} from "@/components/comercial/crm";
import { Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { ContatoCrm, TipoRegistro } from "@/lib/tipos";

// As pessoas das empresas. O decisor é quem o negócio precisa convencer; a
// supressão vale aqui também: e-mail ou telefone de quem pediu para sair não
// entra, nem por edição.

export default function Contatos() {
  const [busca, setBusca] = useState("");
  const [dados, setDados] = useState<{
    total: number;
    itens: ContatoCrm[];
  } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ficha, setFicha] = useState<{ tipo: TipoRegistro; id: number } | null>(
    null,
  );
  const [novo, setNovo] = useState(false);
  const [excluir, setExcluir] = useState<ContatoCrm | null>(null);
  const termo = useAtrasado(busca);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .crmContatos({ busca: termo })
      .then((d) => {
        setDados(d);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [termo]);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const salvar =
    (id: number, campo: string) => async (v: string | boolean | null) => {
      await api.crmEditar("contato", id, { [campo]: v });
      carregar();
    };

  return (
    <TelaCrm
      secao="Contatos"
      acoes={
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setNovo(true)}
        >
          + novo contato
        </button>
      }
    >
      <BarraLista busca={busca} onBusca={setBusca} />

      {erro && <Erro>Não consegui carregar os contatos: {erro}</Erro>}
      {dados && dados.total === 0 && !termo ? (
        <Vazio titulo="Nenhum contato ainda">
          A base de prospecção traz a clínica, não a pessoa. Cadastre quem você
          conhecer, de dentro da ficha da empresa ou em &ldquo;+ novo
          contato&rdquo;.
        </Vazio>
      ) : dados && dados.itens.length === 0 ? (
        <div className="card text-[14px] text-muted">
          Nenhum contato bate com a busca.
        </div>
      ) : dados ? (
        <div className="card overflow-x-auto !p-0">
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr className="card-kicker border-b border-divider text-neutral-500">
                <th className={`${th} pl-4`}>Nome</th>
                <th className={th}>Empresa</th>
                <th className={th}>Cargo</th>
                <th className={th}>Decisor</th>
                <th className={th}>E-mail</th>
                <th className={th}>Telefone</th>
                <th className={`${th} pr-4`} />
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => setFicha({ tipo: "contato", id: c.id })}
                  className="cursor-pointer border-t border-divider first:border-t-0 hover:bg-[color-mix(in_srgb,var(--color-text)_4%,transparent)]"
                >
                  <td className={`${td} pl-4 font-medium text-text`}>
                    {c.nome}
                  </td>
                  <td className={td}>
                    {c.empresa_id ? (
                      <button
                        type="button"
                        className="text-left text-muted hover:text-accent"
                        onClick={(ev) => {
                          ev.stopPropagation();
                          setFicha({ tipo: "empresa", id: c.empresa_id! });
                        }}
                      >
                        {c.empresa_nome}
                      </button>
                    ) : (
                      <span className="text-neutral-500">—</span>
                    )}
                  </td>
                  <td className={td}>
                    <Celula valor={c.cargo} onSalvar={salvar(c.id, "cargo")} />
                  </td>
                  <td className={td}>
                    <Celula
                      valor={c.decisor}
                      tipo="sim_nao"
                      onSalvar={salvar(c.id, "decisor")}
                    />
                  </td>
                  <td className={td}>
                    <Celula
                      valor={c.email}
                      tipo="email"
                      onSalvar={salvar(c.id, "email")}
                    />
                  </td>
                  <td className={`${td} tnum`}>
                    <Celula
                      valor={c.telefone}
                      tipo="telefone"
                      onSalvar={salvar(c.id, "telefone")}
                    />
                  </td>
                  <td className={`${td} pr-4 text-right`}>
                    <button
                      type="button"
                      className="text-[12px] text-neutral-500 hover:text-[#e07f86]"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        setExcluir(c);
                      }}
                    >
                      excluir
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {dados && dados.itens.length > 0 && (
        <p className="tnum mt-3 text-[12px] text-neutral-500">
          {plural(dados.total, "contato", "contatos")}
        </p>
      )}

      {ficha && (
        <FichaCrm
          tipo={ficha.tipo}
          id={ficha.id}
          onFechar={() => setFicha(null)}
          onMudou={carregar}
        />
      )}
      {novo && (
        <FormCrm
          tipo="contato"
          onFechar={() => setNovo(false)}
          onSalvo={(id) => {
            carregar();
            setFicha({ tipo: "contato", id });
          }}
        />
      )}
      {excluir && (
        <Dialogo
          titulo="Excluir contato"
          descricao={`Excluir "${excluir.nome}"? Os negócios com ele ficam, sem o contato.`}
          confirmar="excluir"
          perigo
          onConfirmar={async () => {
            const alvo = excluir;
            setExcluir(null);
            try {
              await api.crmExcluir("contato", alvo.id);
              ok(`${alvo.nome} excluído`);
              carregar();
            } catch (e) {
              falhou("Não excluí", e);
            }
          }}
          onCancelar={() => setExcluir(null)}
        />
      )}
      {aviso && (
        <Aviso texto={aviso.texto} erro={aviso.erro} onFechar={fechar} />
      )}
    </TelaCrm>
  );
}
