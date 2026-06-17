"""
Lightweight logging helpers — all wrapped in try/except so they never
break the main request flow if the analytics DB table is unavailable.
"""


def _session_key(request):
    try:
        if not request.session.session_key:
            request.session.create()
        return request.session.session_key or ''
    except Exception:
        return ''


def _user(request):
    try:
        return request.user if request.user.is_authenticated else None
    except Exception:
        return None


def log_search(request, query: str, result_count: int = 0):
    try:
        from .models import SearchLog
        SearchLog.objects.create(
            query=query[:300],
            result_count=result_count,
            user=_user(request),
            session_key=_session_key(request),
        )
    except Exception:
        pass


def log_view(request, content_type: str, object_id: int, object_name: str = ''):
    try:
        from .models import ViewLog
        ViewLog.objects.create(
            content_type=content_type,
            object_id=object_id,
            object_name=object_name[:250],
            user=_user(request),
            session_key=_session_key(request),
        )
    except Exception:
        pass


def log_download(request, content_type: str, object_id=None, object_name: str = ''):
    try:
        from .models import DownloadLog
        DownloadLog.objects.create(
            content_type=content_type,
            object_id=object_id,
            object_name=object_name[:250],
            user=_user(request),
            session_key=_session_key(request),
        )
    except Exception:
        pass


def log_career_engine(request, pathway: str, result_count: int = 0, mean_grade: str = ''):
    try:
        from .models import CareerEngineLog
        CareerEngineLog.objects.create(
            pathway=pathway[:20].lower(),
            result_count=result_count,
            mean_grade=mean_grade[:5],
            user=_user(request),
            session_key=_session_key(request),
        )
    except Exception:
        pass
