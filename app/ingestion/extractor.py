
from pathlib import Path
import re
import fitz

from app.models import Question, stable_question_id



QUESTION_RE = re.compile(
    r"(?im)^[ \t]*QUEST(?:Ã|A)O[ \t]+"
    r"(?:(DISCURSIVA)[ \t]+)?"
    r"0*(\d{1,3})[ \t]*"
    r"(?:[:.\-][ \t]*)?$"
)


def normalize_text(text: str) -> str:
    """Normaliza quebras e espaços sem remover o conteúdo da questão."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_alternatives(statement: str) -> list[str]:
    """
    Reconhece alternativas em formatos como:
    A) Texto
    A. Texto
    A
    Texto da alternativa
    """
    lines = statement.splitlines()
    alternatives = []
    current_label = None
    current_text = []

    label_re = re.compile(r"^\s*([A-E])\s*(?:[).:\-]\s*(.*))?$", re.I)

    for line in lines:
        line = line.strip()
        match = label_re.match(line)

        if match:
            if current_label:
                content = " ".join(current_text).strip()
                alternatives.append(f"{current_label}) {content}".strip())

            current_label = match.group(1).upper()
            initial_text = match.group(2) or ""
            current_text = [initial_text] if initial_text else []
        elif current_label and line:
            current_text.append(line)

    if current_label:
        content = " ".join(current_text).strip()
        alternatives.append(f"{current_label}) {content}".strip())

    return alternatives


def extract_questions(
    pdf_path: Path,
    year: int | None = None,
    course: str = "Não identificado",
    area: str = "Não identificado",
    exam_type: str = "Não identificado"
):
    doc = fitz.open(pdf_path)

    output = []
    current = None
    ordinal = 0
    extraction_methods = {}

    def finish_question():
        nonlocal current, ordinal

        if current is None:
            return

        statement = normalize_text(current["text"])

        if not statement:
            current = None
            return

        ordinal += 1

        if current["type"] == "discursiva":
            question_type = "discursiva"
            alternatives = []
        else:
            question_type = "objetiva"
            alternatives = extract_alternatives(statement)

        pages = current["pages"]
        has_images = any(
            bool(doc[page_number - 1].get_images(full=True))
            for page_number in pages
        )

        # Sinalização explícita: questões anuladas permanecem no acervo.
        annulled = bool(re.search(r"(?i)\bquest(?:ão|ao)\s+anulad[ao]\b|\bquestão\s+sem\s+efeito\b", statement))
        # Referências de mídia são rastreáveis; imagem não é convertida ficticiamente.
        media_refs = []
        media_dir = Path("data/extracted_media") / re.sub(r"[^A-Za-z0-9_.-]", "_", pdf_path.stem)
        for pno in sorted(pages):
            page_obj = doc[pno - 1]
            for image_index, image_info in enumerate(page_obj.get_images(full=True), start=1):
                xref = image_info[0]
                reference = {"page": pno, "image_index": image_index, "xref": xref,
                             "conversion_status": "extracted_requires_semantic_review"}
                try:
                    extracted = doc.extract_image(xref)
                    media_dir.mkdir(parents=True, exist_ok=True)
                    image_path = media_dir / f"page_{pno}_image_{image_index}.{extracted.get('ext', 'bin')}"
                    image_path.write_bytes(extracted["image"])
                    reference["file_path"] = str(image_path)
                    reference["format"] = extracted.get("ext")
                except Exception as exc:
                    reference["extraction_error"] = type(exc).__name__
                media_refs.append(reference)
        structured_media = []
        if re.search(r"[∑∫√≈≤≥≠πθλµαβ]", statement):
            structured_media.append({"format": "latex_candidate", "source": "extracted_text",
                                     "content": statement, "validation_required": True})
        status = "needs_review" if has_images or annulled else "extracted"

        question = Question(
            id=stable_question_id(
                pdf_path.name,
                current["start_page"],
                ordinal,
                statement
            ),
            source_pdf=pdf_path.name,
            source_page=current["start_page"],
            source_pages=sorted(pages),
            question_number=current.get("number"),
            area=area,
            course=course,
            year=year,
            exam_type=exam_type,
            question_type=question_type,
            statement=statement,
            alternatives=alternatives,
            annulled=annulled,
            media_review_required=has_images,
            media_references=media_refs,
            structured_media=structured_media,
            extraction_method=("ocr" if any(extraction_methods.get(p) == "ocr" for p in pages)
                               else "ocr_unavailable" if any(extraction_methods.get(p) == "ocr_unavailable" for p in pages)
                               else "pymupdf_text"),
            extraction_status=status
        )

        output.append(question)
        current = None

    for page_number, page in enumerate(doc, start=1):
        page_text = normalize_text(page.get_text("text"))
        if not page_text:
            # OCR de contingência para páginas digitalizadas; revisão humana continua obrigatória.
            try:
                import pytesseract
                from PIL import Image
                import io
                pix = page.get_pixmap(dpi=220, alpha=False)
                page_image = Image.open(io.BytesIO(pix.tobytes("png")))
                page_text = normalize_text(pytesseract.image_to_string(page_image, lang="por+eng"))
                if page_text:
                    extraction_methods[page_number] = "ocr"
            except Exception:
                extraction_methods[page_number] = "ocr_unavailable"
        else:
            extraction_methods[page_number] = "pymupdf_text"
        if not page_text:
            continue

        matches = list(QUESTION_RE.finditer(page_text))

       
        if not matches:
            if current is not None:
                current["text"] += "\n" + page_text
                current["pages"].add(page_number)
            continue

        # Texto anterior ao primeiro cabeçalho pode ser
        # continuação da questão anterior.
        prefix = page_text[:matches[0].start()].strip()

        if prefix and current is not None:
            current["text"] += "\n" + prefix
            current["pages"].add(page_number)

        for index, match in enumerate(matches):
            finish_question()

            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(page_text)
            )

            block = page_text[match.end():end].strip()

            is_discursive = bool(match.group(1))
            question_number = match.group(2)

            current = {
                "text": block,
                "start_page": page_number,
                "pages": {page_number},
                "number": question_number,
                "type": "discursiva" if is_discursive else "objetiva"
            }

    
    finish_question()

    doc.close()
    return output

