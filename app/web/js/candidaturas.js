/* A página das candidaturas: a tabela, a gaveta e o funil.
 *
 * Existe como página própria desde 20/08/2026. Na tela única a lista de vagas
 * dividia espaço com transcrição, fila, conhecimento e modelo — e ia ficar
 * ilegível assim que as candidaturas passassem de uma dúzia, que é o ponto em
 * que elas começam a valer alguma coisa.
 *
 * A casca (login, sessão, refresco, botão ↻) vem do `sessao.js`, igual à do
 * painel. Aqui só mora o que é desta página.
 */
import { api } from "./api.js";
import * as aviso from "./avisos.js";
import * as blocos from "./blocos.js";
import * as sessao from "./sessao.js";
import { $ } from "./ui.js";
import * as vagas from "./vagas.js";

// Só os dois blocos que esta página tem onde pintar. Buscar fila, conhecimento
// e modelo a cada 15 s para jogar fora seria consulta ao banco sem leitor.
const BLOCOS = "saude,candidaturas";

async function carregar() {
  const dados = await api(`/api/painel?blocos=${BLOCOS}`);
  $("saude").innerHTML = blocos.pintarSaude(dados.saude || {}, dados.acoes_decididas_hoje);
  $("candidaturas").innerHTML = blocos.pintarCandidaturas(dados.candidaturas || {});
  $("rodape").textContent =
    `${dados.usuario?.email || ""} · atualizado ${new Date().toLocaleTimeString("pt-BR")}`;

  // A tabela fica fora do refresco com a gaveta aberta: repintar por baixo de
  // um campo em edição apagaria o que eu estou digitando.
  if (!vagas.temGavetaAberta()) await vagas.carregarTabela();
}

// A tabela avisa quando a lista muda, e o funil acompanha na hora: os dois
// números moram na mesma tela agora, e discordar por 15 s seria visível.
vagas.ligar(carregar);
sessao.ligarAtualizar((erro) => aviso.erro("Não consegui atualizar", { detalhe: erro.message }));
// Fechar a aba com a gaveta aberta é o mesmo dado perdido pela outra porta.
sessao.ligar(carregar, () => vagas.temGavetaAberta());
