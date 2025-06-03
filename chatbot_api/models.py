# models.py
from django.db import models
from django.utils import timezone
from datetime import timedelta, datetime

class ChatSession(models.Model):
    objects = models.Manager()
    
    session_id = models.CharField(max_length=255, unique=True)  # Unique identifier for the session
    chat_history = models.JSONField(default=list, blank=True)  # Stores the chat history as JSON
    state = models.CharField(max_length=20, default="start")  # Default state for the session
    mistake_count = models.IntegerField()  # Counter for mistakes
    selected_language = models.CharField(max_length=20, default="Unknown")  # Add this field
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp for when the session is created
    updated_at = models.DateTimeField(auto_now=True)  # Timestamp for the last update to the session

    def save(self, *args, **kwargs):
        if self.mistake_count is None:
            self.mistake_count = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.session_id)  # Returns the session ID as a string representation

    def get_chat_history(self):
        """Return the chat history in a structured format"""
        return {
            "messages": self.chat_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "current_state": self.state
        }

    def is_session_expired(self):
        """Check if session has been inactive for more than 5 minutes"""
        timeout_duration = timedelta(seconds=30)  # 5 minutes = 300 seconds
        current_time = timezone.now()
        last_updated = timezone.localtime(self.updated_at)
        return current_time - last_updated > timeout_duration


