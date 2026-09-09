from ragbench.core.models import (
    GoldenQuestion,
    QueryExecutionRecord,
    QuestionType,
    RagExecutionStatus,
    SearchMode,
)


def test_golden_question_validation():
    q = GoldenQuestion(
        question="Qual o prazo máximo do MED?",
        question_type=QuestionType.REGULATORY_TIMELINE,
        ground_truth="O prazo máximo é de 30 minutos.",
        source_document="pop_pix.txt",
    )
    assert q.question_type == QuestionType.REGULATORY_TIMELINE
    assert q.source_document == "pop_pix.txt"


def test_query_execution_record_defaults():
    record = QueryExecutionRecord(
        index=1,
        query="Teste de consulta",
        response="Resposta gerada",
        mode=SearchMode.HYBRID,
    )
    assert record.status == RagExecutionStatus.SUCCESS
    assert record.mode == SearchMode.HYBRID
    assert record.total_latency_seconds == 0.0
    assert record.similarity_score is None
