"""A fila de aprovação — onde o sistema para e espera por mim.

É o terceiro grau de autonomia do plano (§2): o agente **observa** e **prepara**
sozinho; **executar** é decisão minha. É isso que torna seguro deixar um modelo
de 4B escrever e-mail em meu nome — ele nunca envia.

E é aqui que nasce o dataset da F9, sem esforço extra:

    texto_gerado  o que a IA escreveu
    texto_final   o que eu de fato mandei

Cada edição minha antes de aprovar vira um par de preferência. Cem revisões
viradas em cem pares — produzidos por uso normal, não por sessão de rotulagem.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin

# Terminal em qualquer um dos três: decisão tomada é registro histórico, e par
# de treino não pode mudar de valor depois que foi contado.
STATUS = ("pendente", "aprovada", "editada", "rejeitada")
DECIDIDOS = ("aprovada", "editada", "rejeitada")


class AcaoPendente(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "acao_pendente"

    agente: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'email' | 'curriculo' | 'msg_recrutador' — também é a `tarefa` do exemplo
    # de estilo, quando a ação é aprovada.
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    # O que aparece no card. Sai do agente, nunca do LLM: card sem título é
    # card ilegível, e não vale gastar inferência para escrever um.
    titulo: Mapped[str] = mapped_column(Text, nullable=False)

    # Tudo que o executor da F6 vai precisar (destinatário, assunto, anexos).
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Por que esta ação existe. Vai para `exemplo_estilo.contexto` na aprovação
    # e é o que o few-shot compara na hora de escolher exemplo.
    contexto: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pendente", server_default="pendente"
    )
    texto_gerado: Mapped[str | None] = mapped_column(Text)
    texto_final: Mapped[str | None] = mapped_column(Text)
    # Por que rejeitei. O sinal mais barato de coletar e o mais caro de
    # reconstruir depois — em três meses ninguém lembra do motivo.
    motivo: Mapped[str | None] = mapped_column(Text)

    ai_call_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_calls.id"))
    # 'vaga:<uuid>', 'contato:<uuid>' — o mesmo formato do resto do sistema.
    alvo_ref: Mapped[str | None] = mapped_column(String(120))

    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decidida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # A consulta da tela: pendentes, mais antigas primeiro.
        Index("ix_acao_pendente_status_criada", "status", "criada_em"),
        Index("ix_acao_pendente_agente_tipo", "agente", "tipo"),
        Index("ix_acao_pendente_alvo_ref", "alvo_ref"),
    )

    @property
    def decidida(self) -> bool:
        return self.status in DECIDIDOS

    @property
    def texto(self) -> str | None:
        """O texto que vale: o meu, se editei; o da IA, se não."""
        return self.texto_final or self.texto_gerado

    def __repr__(self) -> str:
        return f"<Acao {self.agente}/{self.tipo} {self.status} {self.titulo[:40]!r}>"
