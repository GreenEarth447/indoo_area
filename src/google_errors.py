from __future__ import annotations

from typing import Any


def format_google_error(api_name: str, data: dict[str, Any]) -> str:
    status = data.get("status", "UNKNOWN")
    msg = data.get("error_message", "")
    lines = [f"{api_name} failed: {status}"]
    if msg:
        lines.append(f"Google says: {msg}")
    lines.append(_hint_for_status(status, msg))
    return "\n".join(lines)


def _hint_for_status(status: str, error_message: str) -> str:
    em = (error_message or "").lower()
    if status == "REQUEST_DENIED":
        if "not authorized to use this service" in em or "api restrictions" in em:
            return "\n".join(
                [
                    "Check API key restrictions:",
                    "  https://console.cloud.google.com/apis/credentials",
                    "  Allow: Geocoding, Maps Static, Street View Static",
                    "  Or use 'Don't restrict key' for local testing",
                ]
            )
        hints = [
            "Enable Geocoding, Maps Static, Street View Static APIs",
            "Enable billing: https://console.cloud.google.com/billing",
            "Key restrictions: None or IP (not HTTP referrers for Python)",
        ]
        if "referer" in em:
            hints.append("Remove HTTP referrer restriction for server-side use")
        if "billing" in em:
            hints.append("Billing not enabled on project")
        return "\n".join(hints)
    if status == "OVER_QUERY_LIMIT":
        return "Quota exceeded."
    return "See Google Maps Platform documentation."
