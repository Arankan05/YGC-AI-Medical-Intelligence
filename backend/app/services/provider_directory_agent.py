"""
The User-Agent this application sends to the OpenStreetMap services.

Both the Nominatim usage policy and the Overpass API ask that a client identify
the application making the request, and offer a way to get in touch before
resorting to blocking it. A generic client string is grounds for being blocked,
and being blocked takes provider search down entirely.

The contact is configuration rather than a constant, because a contact point
that is not real is worse than none: it satisfies the letter of the policy while
guaranteeing nobody can actually reach us. The default therefore identifies the
application and its purpose and claims no contact address at all; set
PROVIDER_DIRECTORY_CONTACT to a genuine URL or mailto: before running against
the public instances.
"""

from typing import Optional

APP_NAME = "MediGuardianAI"
APP_VERSION = "0.1"
APP_PURPOSE = "patient healthcare provider search"


def build_user_agent(contact: Optional[str] = None) -> str:
    """
    Builds the User-Agent header value.

    With a contact configured:
        "MediGuardianAI/0.1 (patient healthcare provider search; +https://example.org)"
    Without one:
        "MediGuardianAI/0.1 (patient healthcare provider search)"

    A blank or whitespace-only contact is treated as absent rather than emitted
    as an empty marker.
    """
    details = [APP_PURPOSE]

    cleaned = (contact or "").strip()
    if cleaned:
        details.append(f"+{cleaned}")

    return f"{APP_NAME}/{APP_VERSION} ({'; '.join(details)})"
