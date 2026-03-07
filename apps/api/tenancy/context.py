from contextvars import ContextVar

current_org = ContextVar("current_org", default=None)
in_request_context = ContextVar("in_request_context", default=False)