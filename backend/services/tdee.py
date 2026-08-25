"""TDEE Calculator + Macro Split"""


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    if gender.lower() == "male":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very": 1.725,
    "extreme": 1.9,
}

GOAL_ADJUSTMENTS = {
    "lose200": -200,
    "lose500": -500,
    "maintain": 0,
    "gain200": 200,
    "gain500": 500,
    "custom": 0,  # adjustment set separately
}

# Default macro splits per goal type
DEFAULT_MACRO_SPLITS = {
    "lose200": {"protein": 30, "carbs": 30, "fat": 40},
    "lose500": {"protein": 30, "carbs": 30, "fat": 40},
    "maintain": {"protein": 25, "carbs": 40, "fat": 35},
    "gain200": {"protein": 25, "carbs": 45, "fat": 30},
    "gain500": {"protein": 25, "carbs": 45, "fat": 30},
    "custom": {"protein": 25, "carbs": 40, "fat": 35},
}

# Cal per gram
CAL_PER_G = {"protein": 4, "carbs": 4, "fat": 9}


def calculate_tdee(weight_kg: float, height_cm: float, age: int, gender: str, activity_level: str) -> float:
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.2)
    return round(bmr * multiplier)


def calculate_goal(tdee: float, goal_type: str, custom_adj: int = 0) -> int:
    if goal_type == "custom":
        return max(1200, int(tdee + custom_adj))
    adjustment = GOAL_ADJUSTMENTS.get(goal_type, 0)
    return max(1200, int(tdee + adjustment))


def calculate_macros(calories: float, protein_pct: float, carbs_pct: float, fat_pct: float) -> dict:
    """Convert calorie goal + % split into grams."""
    return {
        "protein_g": round((calories * protein_pct / 100) / CAL_PER_G["protein"]),
        "carbs_g": round((calories * carbs_pct / 100) / CAL_PER_G["carbs"]),
        "fat_g": round((calories * fat_pct / 100) / CAL_PER_G["fat"]),
        "protein_cal": round(calories * protein_pct / 100),
        "carbs_cal": round(calories * carbs_pct / 100),
        "fat_cal": round(calories * fat_pct / 100),
    }


def get_default_macros(goal_type: str, daily_calories: float) -> dict:
    """Get default macro split for a goal type."""
    split = DEFAULT_MACRO_SPLITS.get(goal_type, DEFAULT_MACRO_SPLITS["maintain"])
    macros = calculate_macros(daily_calories, split["protein"], split["carbs"], split["fat"])
    macros["protein_pct"] = split["protein"]
    macros["carbs_pct"] = split["carbs"]
    macros["fat_pct"] = split["fat"]
    return macros


ACTIVITY_LABELS = {
    "sedentary": "Sedentary (desk job, no exercise)",
    "light": "Light (1-3 days/week)",
    "moderate": "Moderate (3-5 days/week)",
    "very": "Very Active (6-7 days/week)",
    "extreme": "Extreme (athlete / physical labor)",
}

GOAL_LABELS = {
    "lose200": "Lose Weight (−200 cal/day)",
    "lose500": "Lose Weight (−500 cal/day)",
    "maintain": "Maintain Weight",
    "gain200": "Gain Weight (+200 cal/day)",
    "gain500": "Gain Weight (+500 cal/day)",
    "custom": "Custom Adjustment",
}
