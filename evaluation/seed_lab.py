"""Insere somente fixtures sintéticas em índice vazio, com identidade worker."""
import argparse
from app.worker.consumer import ensure_index, es, INDEX
from app.models import Question


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-synthetic", action="store_true", required=True)
    parser.parse_args()
    ensure_index()
    if es.search(index=INDEX, body={"size": 0})["hits"]["total"]["value"]:
        raise SystemExit("Índice não vazio: nenhuma alteração realizada. Use um laboratório novo.")
    courses = [("Computação", "Sistemas de Informação"),
               ("Saúde", "Enfermagem"), ("Engenharias", "Engenharia Ambiental")]
    for number in range(1, 19):
        area, course = courses[(number - 1) % len(courses)]
        question = Question(
            id=f"lab-pessoa2-{number:02d}", source_pdf="FIXTURE_SINTETICA_NAO_OFICIAL.pdf",
            source_page=number, year=2021 if number % 2 else 2022,
            area=area, course=course, exam_type="CE", question_type="objetiva",
            statement=f"Questão sintética {number}: como a tecnologia contribui para ética e sustentabilidade?",
            alternatives=["A) Avaliar impactos sociais.", "B) Ignorar os impactos."],
            answer_key="A", competencies=["Ética"], knowledge_objects=["Tecnologia", "Sustentabilidade"],
            extraction_status="synthetic_fixture",
        )
        es.index(index=INDEX, id=question.id, document=question.model_dump(), refresh="wait_for")
    print("18 fixtures sintéticas indexadas pelo principal worker; nenhum PDF oficial foi utilizado.")


if __name__ == "__main__":
    main()
