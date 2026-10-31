import { redirect } from "next/navigation";

// A lista de leads virou a tela Negócios (kanban e lista). A página de um lead
// (`/comercial/leads/[id]`) continua: é a página completa do negócio, com o
// Pesquisador e o Redator.
export default function Leads() {
  redirect("/comercial/negocios");
}
