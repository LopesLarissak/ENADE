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
