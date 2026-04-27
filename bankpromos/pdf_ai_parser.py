import base64
import json
import logging
import os
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from bankpromos.core.models import PromotionModel

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4o"

DEFAULT_PROMPT = """Eres un experto en analizar documentos de promociones bancarias en Paraguay.
Analiza esta imagen de un PDF de promociones y extrae toda la información de cada promoción.
Para cada promoción devuelve:
1. título/descripcion del beneficio
2. porcentaje de descuento o reintegro
3. número de cuotas sin intereses (si aplica)
4. categoría (Combustible, Supermercados, Gastronomía, Indumentaria, Tecnología, Salud, Hogar, Viajes, Belleza, Entretenimiento, Educación, General)
5. nombre del comercio o cadena (ej: Shell, Copetrol, Stock, etc.)
6. monto del tope/tope máximo en guaraníes
7. días válidos (lunes, martes, miercoles, jueves, viernes, sabado, domingo)
8. método de pago (Visa, Mastercard, etc.)
9. fecha de vigencia (desde/hasta)
10. condiciones ou requisitos
11. tipo de beneficio (reintegro, descuento, cuotas)

Responde en JSON formato array de objetos.
"""

AI_FIELDS = [
    "title",
    "discount_percent",
    "installment_count",
    "category",
    "merchant_name",
    "cap_amount",
    "valid_days",
    "payment_method",
    "valid_from",
    "valid_to",
    "conditions_text",
    "benefit_type",
]


def get_api_key() -> Optional[str]:
    return os.environ.get("OPENAI_API_KEY")


def _encode_pdf_to_images(pdf_path: str) -> List[bytes]:
    import tempfile

    image_data = []

    try:
        import fitz
    except ImportError:
        try:
            import PyMuPDF
        except ImportError:
            logger.warning("[PDF-AI] PyMuPDF not installed, attempting to use pdf2image")
            return _encode_pdf_fallback(pdf_path)

    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_data = pix.tobytes("png")
            image_data.append(img_data)
        doc.close()
        return image_data
    except Exception as e:
        logger.error(f"[PDF-AI] Error converting PDF: {e}")
        return []


def _encode_pdf_fallback(pdf_path: str) -> List[bytes]:
    try:
        from pdf2image import convert_from_path

        images = convert_from_path(pdf_path, dpi=200)
        image_data = []
        for img in images:
            import io

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_data.append(buffer.getvalue())
        return image_data
    except Exception as e:
        logger.error(f"[PDF-AI] Fallback conversion failed: {e}")
        return []


def _encode_image_to_base64(image_data: bytes) -> str:
    return base64.b64encode(image_data).decode("utf-8")


def _call_openai_vision(
    image_b64: str,
    model: str = DEFAULT_MODEL,
    prompt: str = DEFAULT_PROMPT,
) -> Optional[dict]:
    api_key = get_api_key()
    if not api_key:
        logger.warning("[PDF-AI] OPENAI_API_KEY not set")
        return None

    try:
        import httpx
    except ImportError:
        logger.warning("[PDF-AI] httpx not installed")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                },
            ],
        }
    ]

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.2,
    }

    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60.0,
        )
        response.raise_for_status()
        result = response.json()

        content = result["choices"][0]["message"]["content"]

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        return json.loads(content.strip())
    except Exception as e:
        logger.error(f"[PDF-AI] OpenAI API error: {e}")
        return None


def analyze_pdf_with_vision(
    pdf_path: str,
    bank_id: str = "unknown",
    model: str = DEFAULT_MODEL,
    prompt: str = DEFAULT_PROMPT,
) -> List[dict]:
    image_data = _encode_pdf_to_images(pdf_path)

    if not image_data:
        logger.warning(f"[PDF-AI] No images extracted from {pdf_path}")
        return []

    all_promos = []

    for idx, img_data in enumerate(image_data):
        img_b64 = _encode_image_to_base64(img_data)

        result = _call_openai_vision(img_b64, model, prompt)

        if result:
            if isinstance(result, list):
                promos = result
            elif isinstance(result, dict):
                promos = result.get("promotions", result.get("promos", [result]))
            else:
                continue

            for promo in promos:
                promo["_page"] = idx + 1
                promo["_source_file"] = pdf_path
                promo["_bank_id"] = bank_id

            all_promos.extend(promos)

    return all_promos


def analyze_pdf_url_with_vision(
    pdf_url: str,
    bank_id: str = "unknown",
    model: str = DEFAULT_MODEL,
    prompt: str = DEFAULT_PROMPT,
) -> List[dict]:
    try:
        import httpx

        response = httpx.get(pdf_url, timeout=30.0)
        response.raise_for_status()

        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        try:
            result = analyze_pdf_with_vision(temp_path, bank_id, model, prompt)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        return result
    except Exception as e:
        logger.error(f"[PDF-AI] Failed to fetch PDF from URL: {e}")
        return []


def _parse_amount(value) -> Optional[Decimal]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if value > 0:
            return Decimal(int(value))

    if isinstance(value, str):
        clean = value.replace(".", "").replace(",", "").replace("Gs", "").replace(" ", "")
        try:
            return Decimal(int(clean))
        except:
            pass

    return None


def _parse_date(value) -> Optional[date]:
    if not value:
        return None

    import re
    from datetime import datetime

    patterns = [
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})",
        r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, str(value))
        if match:
            try:
                d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
                y = 2000 + y if y < 100 else y
                return date(y, m, d)
            except:
                pass

    return None


def _parse_valid_days(value) -> List[str]:
    if not value:
        return []

    if isinstance(value, list):
        return [str(d).lower().strip() for d in value]

    if isinstance(value, str):
        value = value.lower()
        days = []
        day_map = {
            "lunes": "lunes",
            "martes": "martes",
            "miercoles": "miercoles",
            "jueves": "jueves",
            "viernes": "viernes",
            "sabado": "sabado",
            "domingo": "domingo",
        }
        for day, target in day_map.items():
            if day in value:
                days.append(target)
        return days

    return []


def ai_response_to_promotion(
    promo_data: dict,
    bank_id: str,
    source_url: str = "",
) -> Optional[PromotionModel]:
    title = promo_data.get("title") or promo_data.get("titulo")
    if not title:
        return None

    discount = _parse_amount(promo_data.get("discount_percent") or promo_data.get("descuento"))
    if discount is None:
        discount = _parse_amount(promo_data.get("reintegro"))

    installment = promo_data.get("installment_count") or promo_data.get("cuotas")
    if isinstance(installment, str):
        try:
            installment = int(installment)
        except:
            installment = None

    cap = _parse_amount(promo_data.get("cap_amount") or promo_data.get("tope"))

    category = promo_data.get("category") or promo_data.get("categoria")
    if category:
        category = category.title()

    merchant = promo_data.get("merchant_name") or promo_data.get("comercio")
    if merchant:
        merchant = merchant.title()

    benefit_type = promo_data.get("benefit_type") or promo_data.get("tipo_beneficio")
    if benefit_type:
        benefit_type = benefit_type.lower()

    valid_days = _parse_valid_days(promo_data.get("valid_days") or promo_data.get("dias"))

    valid_from = _parse_date(promo_data.get("valid_from") or promo_data.get("vigencia_desde"))
    valid_to = _parse_date(promo_data.get("valid_to") or promo_data.get("vigencia_hasta"))

    payment_method = promo_data.get("payment_method") or promo_data.get("metodo_pago")
    if payment_method:
        payment_method = payment_method.title()

    conditions = promo_data.get("conditions_text") or promo_data.get("condiciones")

    return PromotionModel(
        bank_id=bank_id,
        title=title,
        merchant_name=merchant,
        category=category,
        benefit_type=benefit_type,
        discount_percent=discount,
        installment_count=installment,
        valid_days=valid_days,
        valid_from=valid_from,
        valid_to=valid_to,
        source_url=source_url,
        raw_text=json.dumps(promo_data),
        raw_data={
            "source": "ai_vision",
            "extraction_confidence": 0.85,
            "page": promo_data.get("_page"),
        },
        cap_amount=cap,
        payment_method=payment_method,
        conditions_text=conditions,
    )


def analyze_pdf_and_convert(
    pdf_path: str,
    bank_id: str = "unknown",
    source_url: str = "",
    model: str = DEFAULT_MODEL,
) -> List[PromotionModel]:
    raw_promos = analyze_pdf_with_vision(pdf_path, bank_id, model)

    if not raw_promos:
        return []

    promotions = []
    for promo_data in raw_promos:
        promo = ai_response_to_promotion(promo_data, bank_id, source_url)
        if promo:
            promotions.append(promo)

    return promotions


def analyze_pdf_url_and_convert(
    pdf_url: str,
    bank_id: str = "unknown",
    model: str = DEFAULT_MODEL,
) -> List[PromotionModel]:
    raw_promos = analyze_pdf_url_with_vision(pdf_url, bank_id, model)

    if not raw_promos:
        return []

    promotions = []
    for promo_data in raw_promos:
        promo = ai_response_to_promotion(promo_data, bank_id, pdf_url)
        if promo:
            promotions.append(promo)

    return promotions