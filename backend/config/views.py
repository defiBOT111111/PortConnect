import io
import json
import base64
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pdf2image import convert_from_bytes
from openai import OpenAI
from pydantic import BaseModel

# OpenAI クライアント初期化
client = OpenAI()

# Structured Outputs 用の Pydantic モデル定義
class DraftBLData(BaseModel):
    gross_weight: str
    package_count: str

@csrf_exempt
def check_discrepancies(request):
    # 1. CORS Preflight (OPTIONS) リクエストの許可
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = '*'
        return response

    if request.method != 'POST':
        return JsonResponse({'error': 'POSTリクエストのみ受け付けています'}, status=400)

    try:
        # 2. リクエストからデータ・ファイルの取得
        si_data_raw = request.POST.get('si_data')
        si_data = json.loads(si_data_raw) if si_data_raw else {}

        pdf_file = request.FILES.get('file')
        if not pdf_file:
            response = JsonResponse({'error': 'PDFファイルが添付されていません'}, status=400)
            response['Access-Control-Allow-Origin'] = '*'
            return response

        # 3. PDFを画像変換（1ページ目）
        pdf_bytes = pdf_file.read()
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)

        buffer = io.BytesIO()
        images[0].save(buffer, format="PNG")
        base64_image = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # 4. OpenAI Vision API による抽出 (Structured Outputs)
        completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Draft B/Lの画像から指定された項目を正確に抽出してください。"
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "このDraft B/Lからデータを抽出してください。"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                    ]
                }
            ],
            response_format=DraftBLData,
        )

        extracted_bl = completion.choices[0].message.parsed

        # 5. S/I データと Draft B/L データの照合
        discrepancies = []
        si_values = si_data.get('values', [[]])
        
        # 選択セルの1列目をGross Weightとして比較
        if len(si_values) > 0 and len(si_values[0]) > 0:
            si_weight = str(si_values[0][0]).replace(',', '').strip()
            bl_weight = str(extracted_bl.gross_weight).replace(',', '').strip()

            if si_weight != bl_weight:
                discrepancies.append({
                    "field": "Gross Weight",
                    "si_value": si_weight,
                    "bl_value": extracted_bl.gross_weight
                })

        # 6. 結果レスポンス作成
        res_data = {
            "status": "success",
            "has_discrepancies": len(discrepancies) > 0,
            "discrepancies": discrepancies,
            "extracted_bl_data": extracted_bl.model_dump()
        }

        response = JsonResponse(res_data)
        response['Access-Control-Allow-Origin'] = '*'
        return response

    except json.JSONDecodeError:
        response = JsonResponse({'error': 'si_data のJSONフォーマットが不正です'}, status=400)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    except Exception as e:
        response = JsonResponse({'error': f'処理中にエラーが発生しました: {str(e)}'}, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response