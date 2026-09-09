"""Seed ~150 common SG/MY food items into the food database."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.models import SessionLocal, FoodItem

FOODS = [
    # === Rice dishes ===
    ("Chicken Rice (Braised)", "鸡饭", "rice", "1 plate", 600, 25, 70, 15, 1),
    ("Chicken Rice (Roasted)", "烧鸡饭", "rice", "1 plate", 600, 27, 68, 14, 1),
    ("Hainanese Curry Rice", "海南咖喱饭", "rice", "1 plate", 750, 22, 85, 35, 2),
    ("Nasi Lemak", "椰浆饭", "rice", "1 plate", 650, 18, 70, 32, 3),
    ("Nasi Padang", "巴东饭", "rice", "1 plate", 750, 25, 75, 38, 2),
    ("Nasi Briyani (Chicken)", "鸡腿饭", "rice", "1 plate", 700, 28, 78, 30, 2),
    ("Nasi Briyani (Mutton)", "羊肉饭", "rice", "1 plate", 750, 30, 78, 34, 2),
    ("Claypot Rice", "瓦煲鸡饭", "rice", "1 bowl", 750, 28, 82, 32, 2),
    ("Economy Rice (3 dishes + rice)", "杂菜饭", "rice", "1 plate", 700, 22, 75, 32, 4),
    ("Fried Rice", "炒饭", "rice", "1 plate", 680, 20, 80, 30, 1),
    ("Yang Zhou Fried Rice", "扬州炒饭", "rice", "1 plate", 700, 22, 82, 32, 1),
    ("Duck Rice", "鸭饭", "rice", "1 plate", 620, 24, 72, 28, 2),
    ("Pig Organ Rice", "猪杂饭", "rice", "1 plate", 650, 26, 75, 28, 2),
    ("Char Siew Rice", "叉烧饭", "rice", "1 plate", 650, 24, 72, 28, 2),
    ("Roasted Pork Rice", "烧肉饭", "rice", "1 plate", 680, 26, 72, 32, 2),
    ("Steamed Chicken Rice", "白鸡饭", "rice", "1 plate", 580, 26, 68, 12, 1),
    ("Fish Soup with Rice", "鱼汤配饭", "rice", "1 bowl", 500, 28, 65, 12, 2),
    ("Tomato Rice", "番茄饭", "rice", "1 plate", 550, 16, 72, 20, 3),
    ("Coconut Rice", "椰浆饭", "rice", "1 plate", 600, 14, 68, 30, 2),
    ("Pineapple Rice (Thai)", "菠萝饭", "rice", "1 plate", 620, 18, 75, 28, 3),

    # === Noodle dishes ===
    ("Hokkien Mee", "福建炒虾面", "noodle", "1 plate", 550, 22, 62, 24, 3),
    ("Char Kway Teow", "炒粿条", "noodle", "1 plate", 620, 16, 70, 32, 2),
    ("Laksa", "叻沙", "noodle", "1 bowl", 600, 22, 55, 32, 3),
    ("Penang Laksa", "槟城叻沙", "noodle", "1 bowl", 450, 20, 52, 20, 4),
    ("Mee Rebus", "马来自助面", "noodle", "1 plate", 500, 18, 65, 20, 3),
    ("Mee Siam", "暹罗面", "noodle", "1 plate", 480, 16, 60, 20, 2),
    ("Wanton Mee (Dry)", "云吞面", "noodle", "1 plate", 450, 20, 55, 18, 2),
    ("Wanton Mee (Soup)", "云吞面汤", "noodle", "1 bowl", 400, 22, 50, 14, 2),
    ("Ban Mian", "板面", "noodle", "1 bowl", 450, 22, 60, 14, 3),
    ("Mee Pok (Dry)", "面薄", "noodle", "1 plate", 480, 20, 58, 20, 2),
    ("Mee Pok (Soup)", "面薄汤", "noodle", "1 bowl", 420, 22, 52, 14, 2),
    ("Yee Mee", "伊面", "noodle", "1 plate", 480, 18, 58, 22, 2),
    ("Kway Chap", "粿汁", "noodle", "1 bowl", 550, 24, 60, 22, 3),
    ("Fishball Noodle Soup", "鱼丸面汤", "noodle", "1 bowl", 400, 20, 52, 12, 2),
    ("Fishball Noodle (Dry)", "鱼丸面干", "noodle", "1 plate", 450, 20, 55, 18, 2),
    ("Yong Tau Foo (Soup)", "酿豆腐汤", "noodle", "1 bowl", 380, 18, 48, 12, 5),
    ("Yong Tau Foo (Dry)", "酿豆腐干", "noodle", "1 plate", 420, 18, 52, 16, 4),
    ("Soto Ayam", "索多", "noodle", "1 bowl", 380, 20, 40, 16, 3),
    ("Beef Noodle (Dry)", "牛肉面干", "noodle", "1 plate", 520, 26, 58, 22, 2),
    ("Beef Noodle (Soup)", "牛肉面汤", "noodle", "1 bowl", 480, 28, 52, 18, 2),
    ("Udon Mee (Tempura)", "乌冬面", "noodle", "1 bowl", 450, 16, 62, 14, 3),
    ("Soba (Cold)", "冷荞麦面", "noodle", "1 plate", 320, 14, 48, 4, 4),
    ("Japanese Ramen", "拉面", "noodle", "1 bowl", 550, 24, 60, 24, 2),
    ("Tom Yum Noodle", "冬炎面", "noodle", "1 bowl", 450, 20, 52, 20, 2),
    ("Bak Chor Mee", "肉脞面", "noodle", "1 plate", 500, 22, 58, 22, 2),

    # === Protein dishes ===
    ("Grilled Chicken Breast", "烤鸡胸肉", "protein", "1 serving", 280, 42, 2, 8, 0),
    ("Fried Chicken (2 pcs)", "炸鸡", "protein", "2 pieces", 450, 32, 12, 30, 1),
    ("Chicken Chop", "鸡扒", "protein", "1 serving", 420, 35, 15, 25, 1),
    ("Pork Chop", "猪扒", "protein", "1 serving", 450, 32, 12, 30, 0),
    ("Steamed Fish (with ginger)", "蒸鱼", "protein", "1 serving", 300, 38, 4, 12, 0),
    ("Sweet & Sour Fish", "酸甜鱼", "protein", "1 serving", 380, 28, 18, 22, 1),
    ("Sambal Fish", "参巴鱼", "protein", "1 serving", 350, 30, 8, 22, 2),
    ("Fish & Chips", "鱼和薯条", "protein", "1 serving", 500, 28, 35, 26, 2),
    ("Fish Fillet (Battered)", "炸鱼排", "protein", "1 serving", 380, 26, 18, 22, 1),
    ("Sambal Prawns", "参巴虾", "protein", "1 serving", 320, 28, 10, 18, 2),
    ("Butter Prawns", "奶油虾", "protein", "1 serving", 420, 26, 12, 32, 1),
    ("Black Pepper Crab", "黑胡椒螃蟹", "protein", "1 serving", 450, 32, 8, 30, 1),
    ("Chilli Crab", "辣椒螃蟹", "protein", "1 serving", 500, 30, 14, 34, 1),
    ("Steamed Tofu", "蒸豆腐", "protein", "1 serving", 180, 16, 6, 10, 3),
    ("Deep Fried Tofu", "炸豆腐", "protein", "1 serving", 250, 14, 10, 18, 2),
    ("Mapo Tofu", "麻婆豆腐", "protein", "1 serving", 280, 16, 12, 18, 3),
    ("Hard Boiled Eggs (2)", "水煮蛋", "protein", "2 pieces", 140, 12, 2, 10, 0),
    ("Omelette (2 eggs)", "煎蛋", "protein", "1 serving", 180, 14, 1, 14, 0),
    ("Scrambled Eggs (3)", "炒蛋", "protein", "1 serving", 240, 18, 2, 18, 0),
    ("Salted Egg Chicken", "咸蛋鸡", "protein", "1 serving", 480, 32, 14, 34, 1),
    ("Steamed Saba Fish", "蒸马鲛鱼", "protein", "1 serving", 280, 32, 2, 14, 0),
    ("Teriyaki Chicken", "照烧鸡", "protein", "1 serving", 380, 32, 20, 18, 1),
    ("Tofu with Minced Pork", "肉末豆腐", "protein", "1 serving", 320, 24, 10, 20, 3),

    # === Vegetable & Side dishes ===
    ("Kang Kong (Belacan)", "马来风光", "veg", "1 serving", 120, 4, 6, 8, 3),
    ("Kang Kong (Stir Fried)", "炒空心菜", "veg", "1 serving", 100, 4, 5, 6, 3),
    ("Mixed Vegetables (Stir Fried)", "炒杂菜", "veg", "1 serving", 110, 4, 10, 6, 4),
    ("Broccoli (Garlic)", "蒜蓉西兰花", "veg", "1 serving", 80, 5, 6, 4, 4),
    ("Cai Xin (Stir Fried)", "炒菜心", "veg", "1 serving", 60, 3, 4, 3, 3),
    ("Kailan (Oyster Sauce)", "蚝油菜花", "veg", "1 serving", 90, 5, 8, 4, 3),
    ("Cabbage (Stir Fried)", "炒包菜", "veg", "1 serving", 70, 3, 6, 3, 3),
    ("Lady Fingers (Okra)", "秋葵", "veg", "1 serving", 60, 3, 5, 2, 4),
    ("Tau Gey (Bean Sprouts)", "炒豆芽", "veg", "1 serving", 50, 3, 4, 2, 2),
    ("Long Beans (Stir Fried)", "炒长豆", "veg", "1 serving", 90, 4, 8, 4, 3),
    ("Eggplant (Sambal)", "参巴茄子", "veg", "1 serving", 180, 4, 10, 14, 4),
    ("Green Salad (no dressing)", "沙拉", "veg", "1 bowl", 40, 2, 6, 1, 3),
    ("Green Salad (with dressing)", "沙拉加酱", "veg", "1 bowl", 160, 3, 8, 14, 3),
    ("Roasted Vegetables", "烤蔬菜", "veg", "1 serving", 120, 4, 12, 6, 5),
    ("Coleslaw", "卷心菜沙拉", "veg", "1 serving", 180, 2, 14, 14, 2),
    ("Clam (Hum) Soup", "蛤蜊汤", "veg", "1 bowl", 80, 8, 4, 3, 1),
    ("Seaweed Soup", "紫菜汤", "veg", "1 bowl", 40, 3, 4, 1, 1),
    ("Tofu Soup", "豆腐汤", "veg", "1 bowl", 120, 10, 6, 6, 2),
    ("Winter Melon Soup", "冬瓜汤", "veg", "1 bowl", 60, 3, 6, 2, 2),

    # === Drinks ===
    ("Kopi (Coffee with Condensed Milk)", "咖啡", "drink", "1 cup", 120, 1, 22, 4, 0),
    ("Kopi-C (Coffee with Evaporated Milk)", "咖啡C", "drink", "1 cup", 80, 1, 14, 3, 0),
    ("Kopi-O (Black Coffee)", "咖啡乌", "drink", "1 cup", 25, 1, 4, 0, 0),
    ("Teh (Tea with Condensed Milk)", "奶茶", "drink", "1 cup", 100, 1, 18, 3, 0),
    ("Teh-C (Tea with Evaporated Milk)", "茶C", "drink", "1 cup", 70, 1, 12, 2, 0),
    ("Teh-O (Plain Tea)", "茶乌", "drink", "1 cup", 15, 0, 3, 0, 0),
    ("Milo (Ice)", "美禄冰", "drink", "1 cup", 180, 6, 28, 5, 2),
    ("Milo (Hot)", "美禄热", "drink", "1 cup", 160, 5, 26, 4, 2),
    ("Bubble Tea (Regular)", "珍珠奶茶", "drink", "1 cup", 320, 2, 52, 10, 1),
    ("Bubble Tea (Less Sugar)", "珍珠奶茶少糖", "drink", "1 cup", 240, 2, 38, 8, 1),
    ("Sugarcane Juice", "甘蔗水", "drink", "1 cup", 120, 0, 30, 0, 0),
    ("Lime Juice (Sour Plum)", "酸梅水", "drink", "1 cup", 80, 0, 18, 0, 0),
    ("Fresh Orange Juice", "橙汁", "drink", "1 cup", 110, 1, 26, 0, 1),
    ("Bandung", "玫瑰露", "drink", "1 cup", 140, 1, 30, 2, 0),
    ("Chrysanthemum Tea", "菊花茶", "drink", "1 cup", 60, 0, 14, 0, 0),
    ("Liang Teh (Herbal Tea)", "凉茶", "drink", "1 cup", 40, 0, 10, 0, 0),
    ("Barley Water", "薏米水", "drink", "1 cup", 100, 1, 22, 1, 1),
    ("Soy Milk (Soya Bean)", "豆奶", "drink", "1 cup", 140, 8, 12, 6, 2),
    ("Yakult", "酸奶", "drink", "1 bottle", 65, 1, 14, 0, 0),
    ("Coconut Water", "椰子水", "drink", "1 cup", 45, 0, 10, 0, 0),
    ("Green Tea (Bottled)", "绿茶", "drink", "1 bottle", 0, 0, 0, 0, 0),
    ("100 Plus", "100号", "drink", "1 can", 45, 0, 10, 0, 0),
    ("Coke (Regular)", "可乐", "drink", "1 can", 140, 0, 36, 0, 0),
    ("Coke (Zero)", "零度可乐", "drink", "1 can", 0, 0, 0, 0, 0),
    ("Beer (Tiger/Anchor)", "啤酒", "drink", "1 can", 150, 1, 10, 0, 0),

    # === Snacks & Breakfast ===
    ("Kaya Toast (2 slices)", "咖椰牛油面包", "breakfast", "2 slices", 280, 6, 36, 12, 2),
    ("Soft Boiled Eggs (2)", "半熟蛋", "breakfast", "2 pieces", 140, 12, 2, 10, 0),
    ("Roti Prata (Plain)", "印度煎饼", "breakfast", "1 piece", 200, 5, 28, 8, 1),
    ("Roti Prata (Egg)", "鸡蛋煎饼", "breakfast", "1 piece", 250, 8, 28, 12, 1),
    ("Roti Prata (Cheese)", "芝士煎饼", "breakfast", "1 piece", 300, 10, 28, 16, 1),
    ("Roti John", "印度面包", "breakfast", "1 piece", 350, 18, 28, 18, 2),
    ("Murtabak (Chicken)", "印度煎饼鸡肉", "breakfast", "1 piece", 450, 24, 40, 22, 2),
    ("Murtabak (Mutton)", "印度煎饼羊肉", "breakfast", "1 piece", 480, 26, 40, 26, 2),
    ("Nasi Lemak (Bungkus)", "椰浆饭包", "breakfast", "1 pack", 550, 14, 60, 28, 2),
    ("Economy Bee Hoon", "经济米粉", "breakfast", "1 plate", 450, 12, 55, 20, 2),
    ("Curry Puff (1)", "咖喱角", "snack", "1 piece", 220, 5, 22, 12, 2),
    ("Popiah (1 roll)", "薄饼", "snack", "1 roll", 180, 6, 22, 8, 3),
    ("Satay (10 sticks)", "沙爹", "snack", "10 sticks", 350, 28, 18, 20, 1),
    ("Satay Bee Hoon", "沙爹米粉", "snack", "1 plate", 500, 20, 55, 24, 2),
    ("Carrot Cake (Fried)", "炒萝卜糕", "snack", "1 plate", 380, 8, 42, 20, 2),
    ("Carrot Cake (Steam)", "蒸萝卜糕", "snack", "1 plate", 250, 6, 40, 8, 2),
    ("Soon Kueh (2 pcs)", "笋粿", "snack", "2 pieces", 160, 4, 28, 4, 2),
    ("Ang Ku Kueh (1)", "红龟糕", "snack", "1 piece", 140, 3, 22, 5, 1),
    ("Ondeh Ondeh (3 pcs)", "椰丝糯米饭", "snack", "3 pieces", 180, 2, 28, 8, 2),
    ("Waffle (Plain)", "华夫饼", "snack", "1 piece", 300, 6, 38, 14, 1),
    ("Ice Cream (1 scoop)", "冰淇淋", "snack", "1 scoop", 150, 2, 18, 8, 0),
    ("Chendol", "煎蕊", "snack", "1 bowl", 280, 2, 42, 12, 2),
    ("Ice Kachang", "红豆冰", "snack", "1 bowl", 250, 2, 48, 6, 1),
    ("Bread (2 slices white)", "白面包", "breakfast", "2 slices", 140, 4, 26, 2, 2),
    ("Bread (2 slices wholemeal)", "全麦面包", "breakfast", "2 slices", 150, 6, 26, 2, 4),
    ("Cereal (1 bowl with milk)", "麦片牛奶", "breakfast", "1 bowl", 280, 8, 48, 6, 4),
    ("Oatmeal (1 bowl)", "燕麦粥", "breakfast", "1 bowl", 180, 6, 32, 4, 4),
    ("Granola (1 bowl)", "格兰诺拉", "breakfast", "1 bowl", 350, 8, 48, 14, 5),

    # === Indian ===
    ("Thosai (Plain)", "印度薄饼", "indian", "1 piece", 180, 5, 30, 4, 2),
    ("Thosai (Masala)", "马萨拉薄饼", "indian", "1 piece", 250, 7, 34, 10, 2),
    ("Idli (2 pcs)", "印度蒸糕", "indian", "2 pieces", 130, 4, 26, 2, 2),
    ("Vadai (2 pcs)", "印度豆饼", "indian", "2 pieces", 200, 8, 18, 10, 3),
    ("Chappati (2 pcs)", "印度薄煎饼", "indian", "2 pieces", 220, 6, 38, 4, 4),
    ("Naan (1 plain)", "印度烤饼", "indian", "1 piece", 250, 8, 40, 6, 2),
    ("Naan (Garlic Butter)", "蒜香烤饼", "indian", "1 piece", 320, 8, 40, 14, 2),
    ("Fish Curry (1 bowl)", "鱼咖喱", "indian", "1 bowl", 280, 24, 8, 16, 3),
    ("Chicken Curry (1 bowl)", "鸡咖喱", "indian", "1 bowl", 320, 26, 10, 18, 2),
    ("Dal Curry (1 bowl)", "豆咖喱", "indian", "1 bowl", 180, 12, 20, 4, 6),
    ("Rasam (1 bowl)", "罗宋汤", "indian", "1 bowl", 60, 3, 8, 1, 2),
    ("Tandoori Chicken (1 pc)", "印度烤鸡", "indian", "1 piece", 280, 34, 4, 14, 0),
    ("Chicken 65", "印度炸鸡", "indian", "1 serving", 380, 30, 12, 24, 1),
    ("Mutton Curry", "羊肉咖喱", "indian", "1 serving", 380, 28, 8, 26, 2),
    ("Briyani (Fish)", "鱼饭", "indian", "1 plate", 650, 26, 72, 28, 2),
    ("Puri (2 pcs)", "印度油炸饼", "indian", "2 pieces", 180, 4, 20, 10, 1),
    ("Sambar (1 bowl)", "印度豆汤", "indian", "1 bowl", 120, 6, 16, 3, 5),
    ("Papadum (1)", "印度薄脆", "indian", "1 piece", 40, 2, 4, 2, 1),
]


def seed():
    db = SessionLocal()
    count = 0
    for name, name_zh, category, serving, cal, pro, carb, fat, fib in FOODS:
        existing = db.query(FoodItem).filter(
            FoodItem.name == name
        ).first()
        if not existing:
            db.add(FoodItem(
                name=name, name_zh=name_zh, category=category,
                serving=serving, calories=cal, protein_g=pro,
                carbs_g=carb, fat_g=fat, fiber_g=fib,
                is_verified=True, source="hpb",
            ))
            count += 1
    db.commit()
    db.close()
    print(f"✅ Seeded {count} new food items (total: {len(FOODS)} in dataset)")


if __name__ == "__main__":
    seed()