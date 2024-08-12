from phi.knowledge.text import TextKnowledgeBase
from phi.vectordb.pgvector import PgVector2

db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
intro_knowledge_base = TextKnowledgeBase(
    path="intro.txt",
    # Table name: ai.text_documents
    vector_db=PgVector2(
        collection="text_documents",
        db_url=db_url,
    ),
)

__exports__ = intro_knowledge_base
