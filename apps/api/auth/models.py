from django.db import models


class AuthAuditLog(models.Model):
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    REFRESH_FAILURE = "REFRESH_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"

    EVENT_CHOICES = [
        (LOGIN_SUCCESS, "Login Success"),
        (LOGIN_FAILURE, "Login Failure"),
        (LOGOUT, "Logout"),
        (TOKEN_REFRESH, "Token Refresh"),
        (REFRESH_FAILURE, "Refresh Failure"),
        (RATE_LIMITED, "Rate Limited"),
    ]

    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    username = models.CharField(max_length=150, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    reason = models.TextField(blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["event", "occurred_at"]),
            models.Index(fields=["username", "occurred_at"]),
            models.Index(fields=["ip_address", "occurred_at"]),
        ]
        ordering = ["-occurred_at"]

    def __str__(self):
        return f"{self.event} - {self.username} - {self.occurred_at}"
