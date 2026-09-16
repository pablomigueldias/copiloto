"""estudo — a banca vira tabela, e a questão passa a aceitar imagem

Duas mudanças que vieram do mesmo dia: eu troquei o foco de concurso (Quadrix
sai, Instituto Avança SP entra) e o caderno novo tem questão que só se responde
olhando a figura — topologia de rede, diagrama UML, árvore binária.

`estudo_banca` existe pelo `ativa`. A `origem` já dizia quem aplicou a prova,
mas em texto livre: não dá para pedir ao banco "tire a Quadrix da fila" a
partir de uma string. Com a tabela, pausar é um `UPDATE` e o acervo continua
inteiro — o histórico de repetição espaçada é a única coisa aqui que não se
refaz, e trocar de concurso não pode custá-lo.

O backfill liga as questões que já existem à banca pela **primeira palavra da
`origem`**, que é como o acervo sempre escreveu a procedência. Cespe e Cebraspe
viram uma banca só: são o mesmo aplicador com dois nomes, e mantê-los separados
faria a pausa de um deixar o outro na fila.

Revision ID: 0006_banca_e_imagem
Revises: 0005_estudo
Create Date: 2026-09-14
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0006_banca_e_imagem"
down_revision: str | None = "0005_estudo"
branch_labels = None
depends_on = None

# prefixo da `origem` → nome da banca. O acervo de hoje inteiro cabe aqui; o
# que não casar fica com `banca_id` nulo, que é o certo para questão inédita.
PREFIXOS: tuple[tuple[str, str], ...] = (
    ("Quadrix", "Quadrix"),
    ("Cebraspe", "Cebraspe"),
    ("Cespe", "Cebraspe"),
    ("FCC", "FCC"),
    ("FGV", "FGV"),
    ("VUNESP", "VUNESP"),
    ("IBFC", "IBFC"),
    ("AOCP", "AOCP"),
    ("CESGRANRIO", "CESGRANRIO"),
    ("FUNCAB", "FUNCAB"),
    ("ESAF", "ESAF"),
)


def upgrade() -> None:
    op.create_table(
        "estudo_banca",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("ativa", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ordem", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome"),
    )

    op.add_column("estudo_questao", sa.Column("banca_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_estudo_questao_banca",
        "estudo_questao",
        "estudo_banca",
        ["banca_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_estudo_questao_banca", "estudo_questao", ["banca_id"])

    op.add_column(
        "estudo_questao", sa.Column("imagem", sa.String(length=255), nullable=True)
    )
    op.add_column("estudo_questao", sa.Column("imagem_alt", sa.Text(), nullable=True))

    # ── Backfill ──
    #
    # Só cria a banca que tem questão: uma tabela com onze linhas das quais nove
    # estão vazias é uma tela de filtro cheia de nada.
    conexao = op.get_bind()
    for prefixo, nome in PREFIXOS:
        n = conexao.execute(
            sa.text(
                "SELECT count(*) FROM estudo_questao WHERE origem LIKE :p"
            ),
            {"p": f"{prefixo} %"},
        ).scalar_one()
        if not n:
            continue
        conexao.execute(
            sa.text(
                "INSERT INTO estudo_banca (nome, ativa, ordem) VALUES (:nome, true, 0)"
                " ON CONFLICT (nome) DO NOTHING"
            ),
            {"nome": nome},
        )
        conexao.execute(
            sa.text(
                "UPDATE estudo_questao SET banca_id = ("
                "  SELECT id FROM estudo_banca WHERE nome = :nome"
                ") WHERE origem LIKE :p"
            ),
            {"nome": nome, "p": f"{prefixo} %"},
        )


def downgrade() -> None:
    op.drop_column("estudo_questao", "imagem_alt")
    op.drop_column("estudo_questao", "imagem")
    op.drop_index("ix_estudo_questao_banca", table_name="estudo_questao")
    op.drop_constraint("fk_estudo_questao_banca", "estudo_questao", type_="foreignkey")
    op.drop_column("estudo_questao", "banca_id")
    op.drop_table("estudo_banca")
