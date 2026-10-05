import math
from pyscript import document, when

def floor3(x: float) -> str:
    """小数点第3位以下切り捨て"""
    val = math.floor(round(x, 9) * 1000) / 1000.0
    return f"{val:.3f}"

def get_rank_info(score: int) -> tuple[str, str, str]:
    """スコアに応じたランク名、テキストカラークラス、バッジ背景色を返す"""
    if score >= 1010000:
        return "SSS+", "text-amber-300", "bg-amber-500/20 border-amber-400/50 shadow-[0_0_12px_rgba(251,191,36,0.3)]"
    elif score >= 1007500:
        return "SSS+", "text-amber-400", "bg-amber-500/20 border-amber-500/40"
    elif score >= 1000000:
        return "SSS", "text-pink-400", "bg-pink-500/20 border-pink-500/40"
    elif score >= 990000:
        return "SS", "text-purple-400", "bg-purple-500/20 border-purple-500/40"
    elif score >= 970000:
        return "S", "text-cyan-400", "bg-cyan-500/20 border-cyan-500/40"
    elif score >= 900000:
        return "AAA", "text-emerald-400", "bg-emerald-500/20 border-emerald-500/40"
    else:
        return "OTHER", "text-gray-400", "bg-gray-500/20 border-gray-500/40"

def calc_score_rating(base: float, score: int) -> float:
    """スコア基準のレーティング計算"""
    s = score
    if 970000 <= s < 990000:
        return base + ((s - 970000) / 26.6) * 0.001
    elif s == 990000:
        return base + 0.750 + 0.100
    elif 990000 < s < 1000000:
        return base + ((s - 990000) / 20) * 0.001 + 0.100 + 0.750
    elif s == 1000000:
        return base + 1.250 + 0.200
    elif 1000000 < s < 1007500:
        return base + ((s - 1000000) / 15) * 0.001 + 0.200 + 1.250
    elif s == 1007500:
        return base + 1.750 + 0.300
    elif 1007500 < s < 1010000:
        return base + ((s - 1007500) / 10) * 0.001 + 0.300 + 1.750
    elif s >= 1010000:
        return base + 2.000 + 0.350
    else:
        return base

# クイック入力ボタンの処理
@when("click", ".quick-score")
def set_quick_score(event):
    target = event.currentTarget
    score_val = target.getAttribute("data-score")
    if score_val:
        document.getElementById("score").value = score_val

# 計算実行
@when("click", "#calc-btn")
def on_calculate(event):
    try:
        base_str = document.getElementById("musical").value.strip()
        score_str = document.getElementById("score").value.strip()

        if not base_str or not score_str:
            show_error("譜面定数とスコアを入力してください")
            return

        base = float(base_str)
        score = int(score_str)

        if score < 0 or score > 1010000:
            show_error("スコアは0〜1010000の間で入力してください")
            return

        # 計算実行
        score_rating = calc_score_rating(base, score)
        
        lamp_bonus = 0.0
        if document.getElementById("fb").checked:
            lamp_bonus += 0.050
        if document.getElementById("ab").checked:
            lamp_bonus += 0.300
        if document.getElementById("fc").checked:
            lamp_bonus += 0.100

        total_rating = score_rating + lamp_bonus
        formatted_total = floor3(total_rating)

        # ランク判定
        rank_name, rank_color, rank_badge = get_rank_info(score)

        # UI更新
        document.getElementById("res-rating").textContent = formatted_total
        
        rank_elem = document.getElementById("res-rank")
        rank_elem.textContent = rank_name
        rank_elem.className = f"px-3 py-1 text-sm font-bold rounded-full border {rank_badge} {rank_color}"

        document.getElementById("res-base").textContent = f"{base:.1f}"
        document.getElementById("res-score-bonus").textContent = f"+{score_rating - base:.3f}"
        document.getElementById("res-lamp-bonus").textContent = f"+{lamp_bonus:.3f}"

        # エラーメッセージ非表示
        document.getElementById("error-msg").classList.add("hidden")

    except ValueError:
        show_error("入力値の形式が正しくありません")

def show_error(msg: str):
    err_elem = document.getElementById("error-msg")
    err_elem.textContent = msg
    err_elem.classList.remove("hidden")