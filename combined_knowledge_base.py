from phi.knowledge.combined import CombinedKnowledgeBase
from phi.vectordb.pgvector import PgVector2

from intro_knowledge_base import intro_knowledge_base
from kyndom_knowledge_base import kyndom_knowledge_base

db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

knowledge_base = CombinedKnowledgeBase(
    sources=[
        intro_knowledge_base,
        kyndom_knowledge_base,
    ],
    vector_db=PgVector2(
        # Table name: ai.combined_documents
        collection="combined_documents",
        db_url=db_url,
    ),
)

__exports__ = knowledge_base