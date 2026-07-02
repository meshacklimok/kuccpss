"""
Canonical event names for EventLog (analytics.utils.log_event) and DownloadLog
content_type strings. EventLog.name is a freeform CharField, not a choices
field, so nothing enforces that a writer and a reader agree on the exact
string — these constants are the single source of truth so a typo in one
call site doesn't silently break a dashboard query filtering on the other.
"""

# EventLog.name values
CALCULATOR_RUN = 'calculator_run'
CALCULATOR_SHARE = 'calculator_share'
AI_CHAT_MESSAGE = 'ai_chat_message'
AI_CHAT_PAYWALL_HIT = 'ai_chat_paywall_hit'

# DownloadLog.content_type values (subset also declared in DownloadLog.TYPE_CHOICES)
DOWNLOAD_CLUSTER_PDF = 'cluster_pdf'
DOWNLOAD_CAREER_PDF = 'career_pdf'
