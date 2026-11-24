import argparse
import json
import time
from pathlib import Path
from app.ingestion.extractor import extract_questions
from app.ingestion.producer import publish_questions


def main():
    parser = argparse.ArgumentParser(description="Extrai PDFs do ENADE e publica documentos no Kafka")
    parser.add_argument("--input", required=True, help="Diretório contendo PDFs")
    parser.add_argument("--recursive", action="store_true",
                        help="Procura PDFs também em subdiretórios")
    parser.add_argument("--year", type=int)
    parser.add_argument("--course", default="Não identificado")
    parser.add_argument("--area", default="Não identificado")
    parser.add_argument("--exam-type", default="Não identificado", choices=["FG", "CE", "Não identificado"])
    parser.add_argument("--answer-key", help="JSON opcional: {\"01\":\"A\", \"02\":\"C\"}")
    parser.add_argument("--metadata", help="JSON opcional por número: {\"01\": {\"competencies\":[], \"knowledge_objects\":[]}}")
    args = parser.parse_args()
    root = Path(args.input)
    pdfs = sorted(root.rglob("*.pdf") if args.recursive else root.glob("*.pdf"))
    if not pdfs:
        parser.error(f"Nenhum PDF encontrado em {root}")
    answer_key = json.loads(Path(args.answer_key).read_text(encoding="utf-8")) if args.answer_key else {}
    metadata = json.loads(Path(args.metadata).read_text(encoding="utf-8")) if args.metadata else {}
    total = 0; started = time.perf_counter()
    for pdf in pdfs:
        questions = extract_questions(pdf, args.year, args.course, args.area, args.exam_type)
        for question in questions:
            number = str(question.question_number or "").zfill(2)
            if number in answer_key:
                question.answer_key = str(answer_key[number]).strip()
            if number in metadata:
                question.competencies = metadata[number].get("competencies", [])
                question.knowledge_objects = metadata[number].get("knowledge_objects", [])
                if metadata[number].get("annulled") is True:
                    question.annulled = True
                    question.extraction_status = "needs_review"
        sent = publish_questions(questions)
        total += sent
        print(f"{pdf.name}: {sent} registros publicados")
    elapsed = max(time.perf_counter() - started, 0.000001)
    print(f"TOTAL: {total} documentos | {elapsed:.2f}s | {total / elapsed:.2f} docs/s")

if __name__ == "__main__":
    main()
