import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class WebhookNotifier:
    def __init__(self, webhook_url: str | None, timeout: float) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def notify_external_data(self, event: str, records_count: int) -> None:
        """Deliver best-effort notification after a non-cached external API response."""
        if not self.webhook_url:
            logger.warning("webhook_skipped", extra={"reason": "WEBHOOK_URL is not configured"})
            return
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    self.webhook_url,
                    params={"event": event, "records_count": records_count},
                )
                response.raise_for_status()
            logger.info(
                "webhook_delivered",
                extra={
                    "destination_host": urlparse(self.webhook_url).netloc,
                    "status_code": response.status_code,
                    "records": records_count,
                },
            )
        except httpx.HTTPError:
            logger.warning(
                "webhook_delivery_failed",
                extra={"destination_host": urlparse(self.webhook_url).netloc},
                exc_info=True,
            )
