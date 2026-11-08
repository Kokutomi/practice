"""Canonical topic labels for 年金数理 problems (used for filtering, stats and review)."""

TOPICS = [
    "年金現価・計算基数",
    "生命表・平均余命",
    "定常人口・脱退残存表",
    "昇給率・給与指数",
    "財政方式（Trowbridgeモデル）",
    "加入年齢方式・標準保険料",
    "総合保険料方式",
    "開放基金方式・未積立債務",
    "特別保険料・未積立債務の償却",
    "財政決算・損益（利差等）",
    "財政運営・積立金の推移",
    "制度変更（統合・分割・給付減額）",
]
# legacy labels used by the original sample problems
ALIASES = {"life_annuity": "年金現価・計算基数", "deferred_annuity": "年金現価・計算基数",
           "計算基数・給付現価": "年金現価・計算基数"}


def canonical(topic: str) -> str:
    return ALIASES.get(topic, topic)
