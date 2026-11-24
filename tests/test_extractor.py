import fitz
from app.ingestion.extractor import extract_questions

def test_extract_questions_and_traceability(tmp_path):
    path = tmp_path / "sample.pdf"
    doc = fitz.open(); page = doc.new_page()
    page.insert_textbox((50, 50, 550, 750), "QUESTÃO 01\nEnunciado de teste\nA) Alternativa A\nB) Alternativa B")
    doc.save(path); doc.close()
    questions = extract_questions(path, year=2024, course="Sistemas de Informação", area="Computação", exam_type="CE")
    assert len(questions) == 1
    q = questions[0]
    assert q.source_pdf == "sample.pdf" and q.source_page == 1
    assert q.question_number == "1"
    assert q.course == "Sistemas de Informação"
    assert q.question_type == "objetiva"


def test_question_without_recognized_alternatives_is_not_misclassified(tmp_path):
    path = tmp_path / "discursive-layout.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox((50, 50, 550, 750),
                        "QUESTÃO 02\nExplique a importância da ética na tecnologia.")
    doc.save(path)
    doc.close()

    questions = extract_questions(path, year=2024, course="Sistemas de Informação",
                                  area="Computação", exam_type="CE")
    assert len(questions) == 1
    assert questions[0].question_type == "não_identificada"


def test_annulled_question_with_number_is_preserved_and_flagged(tmp_path):
    path = tmp_path / "annulled.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox((50, 50, 550, 750),
                        "QUESTÃO 03\nQuestão 03 anulada pela comissão.\nA) Uma\nB) Duas")
    doc.save(path)
    doc.close()

    questions = extract_questions(path, year=2024, course="Sistemas de Informação",
                                  area="Computação", exam_type="CE")
    assert len(questions) == 1
    assert questions[0].annulled is True
