def synthesize(outputs: list[dict]) -> dict:
    return {
        "mode": "mock",
        "summary": "[模拟研究结果] 两个角色已完成固定证据讨论。本结果仅用于流程演示，不构成投资建议。",
        "agreements": ["[模拟] 证据链可追溯到本地固定版本。", "[模拟] 缺少真实数据，无法作出现实判断。"],
        "disagreements": ["[模拟] 研究员保留需求假设；质询员认为样本偏差仍未排除。"],
        "open_questions": ["[模拟] 若进入未来研究阶段，应如何引入独立来源并验证反例？"],
        "evidence_refs": sorted({ref for item in outputs for ref in item["evidence_refs"]}),
        "agent_outputs": outputs,
    }
