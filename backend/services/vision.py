"""AI Vision service for food photo analysis"""
import httpx
import json
import os
import base64

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
VISION_MODEL = "google/gemini-2.5-flash"


async def analyze_food_photo(image_path: str) -> dict:
    if not OPENROUTER_API_KEY:
        return {"total_calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "foods": []}

    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    prompt = (
        "Estimate the nutritional content of this food photo. "
        "Respond ONLY with valid JSON: "
        '{"foods": [{"name": "...", "calories": N, "protein_g": N, "carbs_g": N, "fat_g": N}], '
        '"total_calories": N, "total_protein_g": N, "total_carbs_g": N, "total_fat_g": N}'
    )

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": VISION_MODEL,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}},
                        ],
                    }],
                    "max_tokens": 500,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)
            return {
                "total_calories": result.get("total_calories", 0),
                "protein_g": result.get("total_protein_g", 0),
                "carbs_g": result.get("total_carbs_g", 0),
                "fat_g": result.get("total_fat_g", 0),
                "foods": result.get("foods", []),
            }
        except Exception as e:
            return {"total_calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "foods": [], "error": str(e)}


async def analyze_food_text(food_description: str) -> dict:
    if not OPENROUTER_API_KEY:
        return {"total_calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "foods": []}

    prompt = (
        f"Estimate the nutrition for: '{food_description}'. "
        "Respond ONLY with valid JSON: "
        '{"foods": [{"name": "...", "calories": N, "protein_g": N, "carbs_g": N, "fat_g": N}], '
        '"total_calories": N, "total_protein_g": N, "total_carbs_g": N, "total_fat_g": N}'
    )

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-2.5-flash",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                },
            )
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)
            return {
                "total_calories": result.get("total_calories", 0),
                "protein_g": result.get("total_protein_g", 0),
                "carbs_g": result.get("total_carbs_g", 0),
                "fat_g": result.get("total_fat_g", 0),
                "foods": result.get("foods", []),
            }
        except Exception as e:
            return {"total_calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "foods": [], "error": str(e)}