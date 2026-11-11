"""AIC Generic Approval API package.

The human-in-the-loop approval gate for the Autonomous Incident Commander.
See ``main.py`` for the FastAPI app and ``firestore_repo.py`` for the
invariant-enforcing persistence layer (the Admin SDK bypasses
``firestore.rules``, so every rule is re-enforced here in code).
"""

__version__ = "0.1.0"
