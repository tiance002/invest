"""Static, invented fixtures. No network clients or market-data feeds exist."""

EVIDENCE_VERSION = "mock-evidence-v1"
EVIDENCE = (
    {
        "id": "mock-evidence-v1:sample-a",
        "mode": "mock",
        "source": "本地虚构样本 A",
        "statement": "模拟文档描述了一个待核实的需求增长假设；没有真实财务数字。",
    },
    {
        "id": "mock-evidence-v1:sample-b",
        "mode": "mock",
        "source": "本地虚构样本 B",
        "statement": "模拟反例指出样本覆盖不足且存在选择偏差；不能据此推断真实证券表现。",
    },
)


def evidence_bundle() -> dict:
    return {"mode": "mock", "version": EVIDENCE_VERSION, "items": [dict(item) for item in EVIDENCE]}
