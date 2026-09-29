"""Fallible integration boundaries used by routing. External providers are optional in local demo mode."""
from __future__ import annotations
from app.core.config import get_settings

def booking_url():
    settings=get_settings()
    return settings.calendly_booking_url if settings.calendly_booking_url else None
