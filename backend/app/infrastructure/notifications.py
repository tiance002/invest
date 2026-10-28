import logging

from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

logger = logging.getLogger(__name__)
WAKE_KEY = "arena:mock:task-wake"


class Notifications:
    def __init__(self, url: str):
        self.client = Redis.from_url(
            url, socket_connect_timeout=0.3, socket_timeout=2, retry=Retry(NoBackoff(), 0)
        )

    def notify(self, task_id: str) -> bool:
        try:
            # A bounded advisory wake list. The task row, never this list, owns job durability.
            with self.client.pipeline(transaction=True) as pipe:
                pipe.lpush(WAKE_KEY, task_id)
                pipe.ltrim(WAKE_KEY, 0, 999)
                pipe.execute()
            return True
        except RedisError:
            logger.warning("Redis wake unavailable; durable database polling remains active")
            return False

    def wait(self, timeout: int = 1) -> bool:
        try:
            self.client.blpop(WAKE_KEY, timeout=timeout)
            return True
        except RedisError:
            return False

    def healthy(self) -> bool:
        try:
            return bool(self.client.ping())
        except RedisError:
            return False
