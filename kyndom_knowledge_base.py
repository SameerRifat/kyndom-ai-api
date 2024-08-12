from phi.knowledge.json import JSONKnowledgeBase
from phi.vectordb.pgvector import PgVector2

db_url = "postgresql+psycopg://postgres.qsswdusttgzhprqgmaez:Burewala_789@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
kyndom_knowledge_base = JSONKnowledgeBase(
    path="kyndomSocialContentTemplate.json",
    # Table name: ai.json_documents
    vector_db=PgVector2(
        collection="json_documents",
        db_url=db_url,
    ),
)

__exports__ = kyndom_knowledge_base
