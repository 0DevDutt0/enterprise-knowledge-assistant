# app/services/health_service.py
from __future__ import annotations

import logging

from app.rag.generation.llm_client import LLMClient
from app.rag.retrieval.vector_store import VectorStore
from app.services.models import ComponentHealth, ComponentStatus, HealthReport

logger = logging.getLogger(__name__)

_STATUS_RANK = {
    ComponentStatus.OK: 0,
    ComponentStatus.DEGRADED: 1,
    ComponentStatus.ERROR: 2,
}


def _worst(*statuses: ComponentStatus) -> ComponentStatus:
    return max(statuses, key=lambda s: _STATUS_RANK[s])


class HealthService:
    """Aggregates component health into a single HealthReport.

    Checks performed are intentionally shallow (no live API calls) to keep
    the health endpoint fast and side-effect free. Component statuses:

    - vector_store: OK when the store has at least one vector; DEGRADED when
      empty (index not yet built); ERROR on an unexpected exception.
    - llm: OK when the client is configured (non-None). A deep ping would
      require a real API call; that is left to an out-of-band monitoring job.
    """

    def __init__(self, llm_client: LLMClient, vector_store: VectorStore) -> None:
        self._llm_client = llm_client
        self._store = vector_store

    def check(self) -> HealthReport:
        """Run shallow health checks and return an aggregated HealthReport.

        Returns:
            HealthReport with per-component status and an overall status.
        """
        vs_health = self._check_vector_store()
        llm_health = self._check_llm()

        overall = _worst(vs_health.status, llm_health.status)
        report = HealthReport(
            status=overall,
            vector_store=vs_health,
            llm=llm_health,
        )
        logger.info(
            'health_service.check status=%s vs=%s llm=%s',
            overall.value,
            vs_health.status.value,
            llm_health.status.value,
        )
        return report

    def _check_vector_store(self) -> ComponentHealth:
        try:
            size = self._store.size
            if size == 0:
                return ComponentHealth(
                    status=ComponentStatus.DEGRADED,
                    message='Vector store is empty; rebuild the index.',
                )
            return ComponentHealth(
                status=ComponentStatus.OK,
                message=f'{size} vectors loaded.',
            )
        except Exception as exc:
            logger.error('health_service.vector_store_check error=%s', exc)
            return ComponentHealth(
                status=ComponentStatus.ERROR,
                message=f'Vector store error: {exc}',
            )

    def _check_llm(self) -> ComponentHealth:
        if self._llm_client is None:
            return ComponentHealth(
                status=ComponentStatus.ERROR,
                message='LLM client is not configured.',
            )
        return ComponentHealth(
            status=ComponentStatus.OK,
            message='LLM client configured.',
        )
