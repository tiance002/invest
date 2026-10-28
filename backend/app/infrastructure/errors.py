from dataclasses import dataclass


@dataclass(frozen=True)
class SafeError:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


MODEL_TIMEOUT = SafeError("MODEL_TIMEOUT", "模拟模型响应超时；可在尝试次数允许时重试。")
SIMULATED_FAILURE = SafeError("SIMULATED_FAILURE", "已触发预设的首次模拟故障；可手动重试。")
WORKFLOW_FAILED = SafeError("WORKFLOW_FAILED", "模拟研究流程未能完成；请检查保留的执行记录。")
LEASE_EXPIRED = SafeError("LEASE_EXPIRED", "Worker 租约已过期；该尝试已被隔离。")


class ModelFailure(Exception):
    pass


class LostLease(Exception):
    pass
