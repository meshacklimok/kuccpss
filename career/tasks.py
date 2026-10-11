"""
Async tasks for the career app.
Enqueue with: async_task('career.tasks.<name>', arg1, ...)
"""
import logging

logger = logging.getLogger(__name__)


def save_career_snapshot(user_id: str, pathway: str, results: dict) -> None:
    """
    Persist a CareerSessionSnapshot so the dashboard can show recommendations
    even after the session has expired. Called after a career engine run.
    """
    from accounts.models import User, CareerSessionSnapshot

    try:
        user = User.objects.get(pk=user_id)
        CareerSessionSnapshot.objects.create(
            user=user,
            pathway=pathway,
            cluster_points_json=results.get("cluster_points_json", {}),
            mean_grade=results.get("mean_grade", ""),
            aggregate_score=results.get("aggregate_score"),
            total_matches=results.get("total_matches", 0),
            tier_counts_json=results.get("tier_counts_json", {}),
            top_matches_json=results.get("top_matches_json", []),
        )
    except Exception as exc:
        logger.error("save_career_snapshot failed for user %s: %s", user_id, exc)
        raise


def expire_shared_results() -> None:
    """Periodic cleanup — delete expired SharedResult rows."""
    from django.utils import timezone
    from career.models import SharedResult

    deleted, _ = SharedResult.objects.filter(expires_at__lt=timezone.now()).delete()
    if deleted:
        logger.info("expire_shared_results: deleted %d expired shared results", deleted)
