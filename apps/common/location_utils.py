# apps/common/location_utils.py
"""
C++ Location Tracking Server — HTTP Utility
============================================
Thin wrapper around the external C++ server.

Base URL:  http://<SERVER_HOST>:9090   (set LOCATION_SERVER_URL in settings)

Endpoints used:
  POST /api/location/update          ← called by mobile app directly, NOT from here
  GET  /api/location/{employee_id}   ← called here to fetch last known location
"""

import requests
from django.conf import settings


def _base_url() -> str:
    return getattr(settings, "LOCATION_SERVER_URL", "http://localhost:9090").rstrip("/")


def _timeout() -> int:
    """Seconds before we give up waiting for the C++ server."""
    return int(getattr(settings, "LOCATION_SERVER_TIMEOUT", 5))


def get_staff_location(employee_id: str) -> dict:
    """
    Fetch the last known location of a staff / makeup artist.

    Args:
        employee_id: The staff's unique ID string sent to the C++ server (e.g. "D123").

    Returns a dict:
        {
            "success":    bool,
            "employee":   str,
            "lat":        float | None,
            "lng":        float | None,
            "timestamp":  str | None,
            "error":      str | None   ← only present on failure
        }
    """
    url = f"{_base_url()}/api/location/{employee_id}"

    try:
        response = requests.get(url, timeout=_timeout())

        if response.status_code == 200:
            data = response.json()
            return {
                "success":   True,
                "employee":  data.get("Employee", employee_id),
                "lat":       data.get("lat"),
                "lng":       data.get("lng"),
                "timestamp": data.get("timestamp"),
                "error":     None,
            }

        if response.status_code == 404:
            return {
                "success":   False,
                "employee":  employee_id,
                "lat":       None,
                "lng":       None,
                "timestamp": None,
                "error":     "No location data found for this employee",
            }

        return {
            "success":   False,
            "employee":  employee_id,
            "lat":       None,
            "lng":       None,
            "timestamp": None,
            "error":     f"Location server returned HTTP {response.status_code}",
        }

    except requests.exceptions.ConnectionError:
        return {
            "success":   False,
            "employee":  employee_id,
            "lat":       None,
            "lng":       None,
            "timestamp": None,
            "error":     "Cannot reach location server (connection refused)",
        }

    except requests.exceptions.Timeout:
        return {
            "success":   False,
            "employee":  employee_id,
            "lat":       None,
            "lng":       None,
            "timestamp": None,
            "error":     "Location server timed out",
        }

    except Exception as e:
        return {
            "success":   False,
            "employee":  employee_id,
            "lat":       None,
            "lng":       None,
            "timestamp": None,
            "error":     str(e),
        }


def get_bulk_locations(employee_ids: list[str]) -> list[dict]:
    """
    Fetch last known locations for multiple staff members.
    Each member is fetched individually. A failure for one member
    does NOT abort the others — their entry will have success=False.

    Args:
        employee_ids: List of employee ID strings.

    Returns:
        List of location dicts (same shape as get_staff_location).
    """
    return [get_staff_location(eid) for eid in employee_ids]