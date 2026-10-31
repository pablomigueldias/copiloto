"use client";

import { useCallback, useEffect, useState } from "react";

import { Aviso, Dialogo } from "@/components/Dialogo";
import { FichaCrm } from "@/components/comercial/FichaCrm";
import { FormCrm } from "@/components/comercial/FormCrm";
import {
  Celula,
  Pilula,
  Segmentos,
  TelaCrm,
  td,
  th,
  useOpcoes,
} from "@/components/comercial/crm";
import { Erro, Vazio, plural } from "@/components/ui";
import { api } from "@/lib/api";
import { useAtualizar } from "@/lib/atualizar";
import { useAvisos } from "@/lib/avisos";
import type { AtividadeCrm, TipoRegistro } from "@/lib/tipos";

// As tarefas de todos os negócios. As da cadência (pesquisar, escrever,
// enviar, lembrete) nascem sozinhas; ligar, reunião e "outro" são as que eu
// crio à mão. Marcar feita é um clique.

type Situacao = "abertas" | "atrasadas" | "feitas" | "todas";

export default function Atividades() {
  const opcoes = useOpcoes();
  const [situacao, setSituacao] = useState<Situacao>("abertas");
  const [itens, setItens] = useState<AtividadeCrm[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ficha, setFicha] = useState<{ tipo: TipoRegistro; id: number } | null>(
    null,
  );
  const [nova, setNova] = useState(false);
  const [excluir, setExcluir] = useState<AtividadeCrm | null>(null);
  const { aviso, ok, falhou, fechar } = useAvisos();

  const carregar = useCallback(() => {
    api
      .crmAtividades({ situacao })
      .then((a) => {
        setItens(a);
        setErro(null);
      })
      .catch((e) => setErro((e as Error).message));
  }, [situacao]);
  useEffect(() => {
    carregar();
  }, [carregar]);
  useAtualizar(carregar);

  const opTipo = Object.entries(opcoes?.tipo_tarefa ?? {}).map(
    ([valor, rotulo]) => ({ valor, rotulo }),
  );
  const salvar =
    (id: number, campo: string) => async (v: string | boolean | null) => {
      await api.crmEditar("atividade", id, { [campo]: v });
      carregar();
    };

  return (
    <TelaCrm
      secao="Atividades"
      acoes={
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setNova(true)}
        >
          + nova atividade
        </button>
      }
    >
      <div className="mb-4">
        <Segmentos
          rotulo="situação"
          valor={situacao}
          onMudar={setSituacao}
          opcoes={[
            { valor: "abertas", rotulo: "Abertas" },
            { valor: "atrasadas", rotulo: "Atrasadas" },
            { valor: "feitas", rotulo: "Feitas" },
            { valor: "todas", rotulo: "Todas" },
          ]}
        />
      </div>

      {erro && <Erro>Não consegui carregar as atividades: {erro}</Erro>}
      {itens && itens.length === 0 ? (
        <Vazio
          titulo={
            situacao === "atrasadas"
              ? "Nada atrasado"
              : "Nenhuma atividade aqui"
          }
        >
          {situacao === "abertas"
            ? "As tarefas da cadência aparecem aqui sozinhas; as outras, crie em “+ nova atividade” ou de dentro do negócio."
            : undefined}
        </Vazio>
      ) : itens ? (
        <div className="card overflow-x-auto !p-0">
          <table className="w-full border-collapse text-[13.5px]">
            <thead>
              <tr className="card-kicker border-b border-divider text-neutral-500">
                <th className={`${th} w-[36px] pl-4`} />
                <th className={th}>Vence</th>
                <th className={th}>Tipo</th>
                <th className={th}>Descrição</th>
                <th className={th}>Negócio</th>
                <th className={`${th} pr-4`} />
              </tr>
            </thead>
            <tbody>
              {itens.map((a) => (
                <tr
                  key={a.id}
                  className={`border-t border-divider first:border-t-0 ${a.feita_em ? "opacity-60" : ""}`}
                >
                  <td className={`${td} pl-4`}>
                    <input
                      type="checkbox"
                      aria-label={`feita: ${opcoes?.tipo_tarefa[a.tipo] ?? a.tipo} de ${a.negocio_nome}`}
                      checked={!!a.feita_em}
                      onChange={async (e) => {
                        try {
                          await salvar(a.id, "feita")(e.target.checked);
                        } catch (err) {
                          falhou("Não marquei", err);
                        }
                      }}
                    />
                  </td>
                  <td className={`${td} tnum whitespace-nowrap`}>
                    <Celula
                      valor={a.vence_em}
                      exibicao={new Date(
                        `${a.vence_em}T00:00:00`,
                      ).toLocaleDateString("pt-BR")}
                      tipo="data"
                      className={a.atrasada ? "!text-[#e07f86]" : ""}
                      onSalvar={salvar(a.id, "vence_em")}
                    />
                    {a.atrasada && (
                      <span className="ml-2">
                        <Pilula valor="atrasada">atrasada</Pilula>
                      </span>
                    )}
                  </td>
                  <td className={td}>
                    <Celula
                      valor={a.tipo}
                      tipo="opcao"
                      opcoes={opTipo}
                      onSalvar={salvar(a.id, "tipo")}
                    />
                  </td>
                  <td className={`${td} max-w-[320px]`}>
                    <Celula
                      valor={a.descricao}
                      vazio="+ descrição"
                      onSalvar={salvar(a.id, "descricao")}
                    />
                  </td>
                  <td className={td}>
                    <button
                      type="button"
                      className="text-left hover:text-accent"
                      onClick={() =>
                        setFicha({ tipo: "negocio", id: a.lead_id })
                      }
                    >
                      <span className="text-text">{a.negocio_nome}</span>
                      <span className="ml-2 text-[12px] text-neutral-500">
                        {opcoes?.estagio[a.negocio_estagio] ??
                          a.negocio_estagio}
                      </span>
                    </button>
                  </td>
                  <td className={`${td} pr-4 text-right`}>
                    <button
                      type="button"
                      className="text-[12px] text-neutral-500 hover:text-[#e07f86]"
                      onClick={() => setExcluir(a)}
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
      {itens && itens.length > 0 && (
        <p className="tnum mt-3 text-[12px] text-neutral-500">
          {plural(itens.length, "atividade", "atividades")}
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
      {nova && (
        <FormCrm
          tipo="atividade"
          onFechar={() => setNova(false)}
          onSalvo={() => carregar()}
        />
      )}
      {excluir && (
        <Dialogo
          titulo="Excluir atividade"
          descricao="Excluir esta atividade? Para tirar da lista sem apagar, marque como feita."
          confirmar="excluir"
          perigo
          onConfirmar={async () => {
            const alvo = excluir;
            setExcluir(null);
            try {
              await api.crmExcluir("atividade", alvo.id);
              ok("Atividade excluída");
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
