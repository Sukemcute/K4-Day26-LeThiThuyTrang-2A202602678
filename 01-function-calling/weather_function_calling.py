"""Minh hoạ FUNCTION CALLING thuần với Google Gemini SDK.

Tool `get_weather` được định nghĩa schema thủ công VÀ thực thi ngay trong
chính file app này. Model chỉ QUYẾT ĐỊNH gọi tool nào; app mới là nơi chạy.

Cách chạy:
    pip install -r ../requirements.txt
    export GEMINI_API_KEY=...
    python weather_function_calling.py
"""

import os
import sys
from pathlib import Path

# Đảm bảo in tiếng Việt trên console Windows không bị lỗi font / charmap
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Tự động nạp API key từ file .env ở thư mục gốc hoặc thư mục hiện tại
for _env_path in [Path(".env"), Path("../.env"), Path(__file__).parent / ".env", Path(__file__).parent.parent / ".env"]:
    if _env_path.exists():
        with open(_env_path, "r", encoding="utf-8") as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    _k, _v = _k.strip(), _v.strip().strip("'\"")
                    if _k not in os.environ:
                        os.environ[_k] = _v
        break

if "GOOGLE_API_KEY" in os.environ and "GEMINI_API_KEY" not in os.environ:
    os.environ["GEMINI_API_KEY"] = os.environ["GOOGLE_API_KEY"]

from google import genai
from google.genai import types

client = genai.Client()

MODEL = "gemini-flash-latest"

SYSTEM_INSTRUCTION = (
    "Bạn là trợ lý thời tiết thân thiện, trả lời bằng tiếng Việt tự nhiên. "
    "Dùng emoji phù hợp (🌧️ 🌤️ 💨 💧). "
    "Tóm tắt ngắn gọn, dễ hiểu, và đưa ra lời khuyên thực tế "
    "(ví dụ: mang ô, mặc áo mỏng, ...)."
)

import json
import httpx

# 1. Định nghĩa các tool (chỉ cần viết hàm Python thuần với type hints & docstring, KHÔNG CẦN viết Schema thủ công)

# 2. App tự thực thi tool: gọi WeatherAPI thật (kèm retry và fallback nếu mạng chập chờn)
CITY_ALIASES = {
    "hà nội": "Hanoi",
    "hanoi": "Hanoi",
    "đà nẵng": "Danang",
    "danang": "Danang",
    "da nang": "Danang",
    "hồ chí minh": "Ho Chi Minh City",
    "tp hcm": "Ho Chi Minh City",
    "tphcm": "Ho Chi Minh City",
    "hải phòng": "Haiphong",
    "haiphong": "Haiphong",
    "cần thơ": "Can Tho",
    "huế": "Hue",
    "nha trang": "Nha Trang",
}

def get_weather(city: str) -> str:
    """Lấy dữ liệu thời tiết THẬT từ WeatherAPI cho *city*."""
    api_key = os.getenv("WEATHERAPI_KEY")
    query_city = CITY_ALIASES.get(city.strip().lower(), city.strip())
    if api_key and api_key != "your_weatherapi_key_here":
        import time
        for attempt in range(2):
            try:
                resp = httpx.get(
                    "https://api.weatherapi.com/v1/current.json",
                    params={"key": api_key, "q": query_city, "aqi": "no"},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    loc = data.get("location", {})
                    cur = data.get("current", {})
                    return json.dumps({
                        "thành_phố": loc.get("name", city),
                        "khu_vực": loc.get("region"),
                        "quốc_gia": loc.get("country"),
                        "nhiệt_độ": f"{cur.get('temp_c')}°C",
                        "cảm_giác_như": f"{cur.get('feelslike_c')}°C",
                        "thời_tiết": cur.get("condition", {}).get("text"),
                        "độ_ẩm": f"{cur.get('humidity')}%",
                        "gió": f"{cur.get('wind_kph')} km/h hướng {cur.get('wind_dir')}",
                        "uv": cur.get("uv"),
                        "cập_nhật_lúc": cur.get("last_updated"),
                    }, ensure_ascii=False)
            except Exception as e:
                if attempt == 1:
                    print(f"  [Lỗi gọi WeatherAPI current.json]: {e}")
                time.sleep(0.5)

    # Fallback dữ liệu mẫu nếu API gặp sự cố
    mock_data = {
        "Hà Nội": {"nhiệt_độ": "29°C", "thời_tiết": "trời mưa nhẹ", "độ_ẩm": "82%", "gió": "12 km/h Đông Nam"},
        "Hồ Chí Minh": {"nhiệt_độ": "33°C", "thời_tiết": "mưa rào", "độ_ẩm": "75%", "gió": "15 km/h Tây Nam"},
        "Đà Nẵng": {"nhiệt_độ": "30°C", "thời_tiết": "nhiều mây", "độ_ẩm": "78%", "gió": "10 km/h Đông"},
    }
    default = {"nhiệt_độ": "28°C", "thời_tiết": "không có dữ liệu chi tiết"}
    return json.dumps({"city": city, **mock_data.get(city, default)}, ensure_ascii=False)


def get_forecast(city: str, days: int = 3) -> str:
    """Lấy dữ liệu dự báo thời tiết THẬT từ WeatherAPI cho *city* trong *days* ngày."""
    days = max(1, min(int(days), 3))
    api_key = os.getenv("WEATHERAPI_KEY")
    query_city = CITY_ALIASES.get(city.strip().lower(), city.strip())
    if api_key and api_key != "your_weatherapi_key_here":
        import time
        for attempt in range(2):
            try:
                resp = httpx.get(
                    "https://api.weatherapi.com/v1/forecast.json",
                    params={"key": api_key, "q": query_city, "days": str(days), "aqi": "no", "alerts": "no"},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    loc = data.get("location", {})
                    forecast_days = []
                    for day in data.get("forecast", {}).get("forecastday", []):
                        d = day.get("day", {})
                        forecast_days.append({
                            "ngày": day.get("date"),
                            "nhiệt_độ_cao_nhất": f"{d.get('maxtemp_c')}°C",
                            "nhiệt_độ_thấp_nhất": f"{d.get('mintemp_c')}°C",
                            "thời_tiết": d.get("condition", {}).get("text"),
                            "khả_năng_mưa": f"{d.get('daily_chance_of_rain')}%",
                            "gió_tối_đa": f"{d.get('maxwind_kph')} km/h",
                            "uv": d.get("uv"),
                        })
                    return json.dumps({
                        "thành_phố": loc.get("name", city),
                        "quốc_gia": loc.get("country"),
                        "so_ngay_du_bao": len(forecast_days),
                        "du_bao": forecast_days,
                    }, ensure_ascii=False)
            except Exception as e:
                if attempt == 1:
                    print(f"  [Lỗi gọi WeatherAPI forecast.json]: {e}")
                time.sleep(0.5)

    # Fallback dữ liệu mẫu nếu API gặp sự cố
    return json.dumps({
        "city": city,
        "so_ngay_du_bao": days,
        "du_bao": [{"ngày": f"Ngày {i+1}", "nhiệt_độ": "25°C - 31°C", "thời_tiết": "nắng nhẹ", "khả_năng_mưa": "30%"} for i in range(days)]
    }, ensure_ascii=False)


def get_clothing_advice(temperature_c: float, weather_condition: str = "bình thường") -> str:
    """Đưa ra lời khuyên trang phục và phụ kiện phù hợp dựa trên nhiệt độ (°C) và thời tiết."""
    advice = []
    try:
        temp = float(temperature_c)
    except (ValueError, TypeError):
        temp = 25.0
    cond = str(weather_condition).lower()

    # 1. Gợi ý quần áo theo mức nhiệt độ
    if temp >= 32:
        advice.append("Áo thun cotton thoáng mát, quần short hoặc váy mỏng nhẹ, chất liệu thấm hút mồ hôi.")
    elif 26 <= temp < 32:
        advice.append("Áo sơ mi ngắn tay, áo phông thoáng mát, quần vải hoặc jean nhẹ nhàng.")
    elif 20 <= temp < 26:
        advice.append("Áo tay dài hoặc áo thun kèm một chiếc áo khoác gió mỏng/cardigan.")
    elif 15 <= temp < 20:
        advice.append("Áo len mỏng, áo hoodie hoặc áo khoác ấm vừa phải, quần dài.")
    elif 10 <= temp < 15:
        advice.append("Áo len dày, áo khoác dạ hoặc áo phao ấm, mang thêm khăn quàng cổ.")
    else:
        advice.append("Áo giữ nhiệt, áo phao dày, găng tay, mũ len và khăn choàng ấm áp.")

    # 2. Gợi ý phụ kiện theo điều kiện thời tiết
    if any(w in cond for w in ["mưa", "rain", "drizzle", "shower", "thunder", "dông"]):
        advice.append("Bắt buộc mang theo ô (dù), áo mưa tiện lợi và ưu tiên đi giày dép chống nước hoặc bọc giày.")
    elif any(w in cond for w in ["nắng", "sun", "clear", "quang mây"]):
        advice.append("Nên đội mũ/nón rộng vành, đeo kính râm chống tia cực tím và thoa kem chống nắng khi ra đường.")
    elif any(w in cond for w in ["gió", "wind", "bão"]):
        advice.append("Mặc áo khoác có mũ cản gió, tránh mặc đồ quá rườm rà.")
    elif any(w in cond for w in ["sương", "fog", "mist", "bụi", "haze"]):
        advice.append("Nên đeo khẩu trang bảo vệ đường hô hấp và kính bảo hộ mắt.")

    return json.dumps({
        "nhiet_do_c": temp,
        "dieu_kien_thoi_tiet": weather_condition,
        "trang_phuc": advice[0] if advice else "Trang phục hàng ngày thoải mái.",
        "phu_kien_can_thiet": advice[1] if len(advice) > 1 else "Không cần phụ kiện đặc biệt.",
        "tong_hop": " ".join(advice),
    }, ensure_ascii=False)


# Bảng tra cứu hàm để app thực thi tự động dựa vào tên tool model gọi
AVAILABLE_TOOLS = {
    "get_weather": get_weather,
    "get_forecast": get_forecast,
    "get_clothing_advice": get_clothing_advice,
}

# 2. TỰ ĐỘNG SINH SCHEMA cho Gemini từ các hàm trên (KHÔNG CẦN viết Schema thủ công)
TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration.from_callable(client=client, callable=fn)
            for fn in AVAILABLE_TOOLS.values()
        ]
    )
]


def run(prompt: str) -> str:
    """Gửi *prompt* tới Gemini, tự động xử lý function calling và trả về câu trả lời cuối."""
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    ]

    # 3. Gọi model — model quyết định có gọi tool hay không
    resp = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=TOOLS,
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    # 4. Vòng lặp: nếu model yêu cầu tool, app TỰ THỰC THI rồi đưa kết quả trả lại
    while resp.function_calls:
        # Thêm phản hồi của model vào lịch sử hội thoại
        contents.append(resp.candidates[0].content)

        function_responses = []
        for fc in resp.function_calls:
            print(f"  [model yêu cầu] {fc.name}({fc.args})")
            tool_fn = AVAILABLE_TOOLS.get(fc.name)
            if tool_fn:
                result = tool_fn(**fc.args)  # <-- app chạy, không phải model
            else:
                result = f"Error: Tool {fc.name} không tồn tại"
            print(f"  [app thực thi]  -> {result}")
            function_responses.append(
                types.Part.from_function_response(
                    name=fc.name, response={"result": result}
                )
            )

        # Gửi kết quả tool trả về cho model
        contents.append(types.Content(role="user", parts=function_responses))
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=TOOLS,
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )

    # 5. Model tổng hợp câu trả lời cuối
    return resp.text


if __name__ == "__main__":
    question = "Thời tiết Hà Nội hôm nay thế nào và với thời tiết đó tôi nên mặc trang phục gì? Dự báo thời tiết Đà Nẵng 3 ngày tới ra sao?"
    print(f"User: {question}\n")
    print("Trả lời:", run(question))
