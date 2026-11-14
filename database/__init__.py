"""Universal AI GIS Studio — Database and Storage Layer.

SQLite with WAL mode, migrations, indexes, foreign keys, and transactions.
Repository + service layers keep SQL out of UI components.
"""

from .db import Database


__all__ = ["Database", "SCHEMA"]
