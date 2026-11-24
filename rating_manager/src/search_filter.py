"""検索タブの絞り込み（DOM非依存）

ランプの条件は、チェックしたもの全てを満たす譜面に絞る（例：「FB済み」+「未AB」で、FBだけ取れている譜面）。
バージョンは、チェックしたどれかに入る譜面に絞る。未プレイの譜面は「未〜」に含める。
"""

def _ab(rec):
    return bool(rec.get("ab"))


def _fc(rec):
    return bool(rec.get("fc") or rec.get("ab"))  # AB なら FC も取れている


def _fb(rec):
    return bool(rec.get("fb"))


def _abfb(rec):
    return _ab(rec) and _fb(rec)


# (値, 表示名, 判定)。画面には 済み を左列、未 を右列に並べる
LAMP_FILTERS = (
    ("abfb", "ABFB済み", _abfb),
    ("no_abfb", "未ABFB", lambda r: not _abfb(r)),
    ("ab", "AB済み", _ab),
    ("no_ab", "未AB", lambda r: not _ab(r)),
    ("fc", "FC済み", _fc),
    ("no_fc", "未FC", lambda r: not _fc(r)),
    ("fb", "FB済み", _fb),
    ("no_fb", "未FB", lambda r: not _fb(r)),
)
LAMP_TEST = {value: test for value, _, test in LAMP_FILTERS}


def passes(chart: dict, rec: dict, lamps: set, versions: set) -> bool:
    """絞り込みの条件に合う譜面か（lamps・versions が空ならその条件は使わない）"""
    if versions and chart.get("version") not in versions:
        return False
    return all(LAMP_TEST[v](rec) for v in lamps)
