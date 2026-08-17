"""
Shared test configuration.

`app.db.database` builds the SQLAlchemy engine at import time and raises if
DATABASE_URL is unset. Almost every module in the application imports it
transitively - `app.services` reaches it through `app.core.security` - so
without a value present the entire suite fails during collection, before a
single test runs, on any machine that has no backend/.env.

The tests never use this engine: each suite that needs a database builds its own
in-memory SQLite session. The placeholder below exists only to let the module
import. `setdefault` means a real DATABASE_URL already in the environment always
wins, so this cannot mask or override a developer's own configuration.

SQLite is used rather than a plausible-looking PostgreSQL URL so that anything
which did unexpectedly try to connect fails locally and obviously, instead of
reaching for a database server that might actually exist.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
