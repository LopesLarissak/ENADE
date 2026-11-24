from app.models import stable_question_id, Question

def test_idempotent_id():
    assert stable_question_id("prova.pdf", 2, 1, "Questão teste") == stable_question_id("prova.pdf", 2, 1, "Questão teste")

def test_question_preserves_annulled_and_traceability():
    q = Question(id="1", source_pdf="prova.pdf", source_page=4, source_pages=[4, 5],
                 statement="Questão anulada", annulled=True)
    assert q.annulled is True
    assert q.source_pdf == "prova.pdf"
    assert q.source_pages == [4, 5]
