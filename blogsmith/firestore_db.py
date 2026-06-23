"""Firebase initialisation + Firestore access helpers.

One central Firebase project backs the whole service. Users are provisioned on
the Firebase dashboard; this module only reads/writes their data. The Admin SDK
is initialised once (idempotent) and transparently targets the local emulator
when ``FIRESTORE_EMULATOR_HOST`` is set.

Document layout (see plan):
    users/{uid}
    users/{uid}/sites/{siteId}
    users/{uid}/sites/{siteId}/runs/{runId}
    checkpoints/{thread}                # LangGraph Firestore checkpointer
"""

from __future__ import annotations

import logging
import os
import threading

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import CollectionReference, DocumentReference

from blogsmith.config import get_settings

logger = logging.getLogger(__name__)

_init_lock = threading.Lock()
_app: firebase_admin.App | None = None


def init_firebase() -> firebase_admin.App:
    """Initialise the Admin SDK exactly once. Safe to call repeatedly."""
    global _app
    if _app is not None:
        return _app
    with _init_lock:
        if _app is not None:
            return _app
        settings = get_settings()

        # Wire emulator env vars through if configured (dev / CI).
        if settings.firestore_emulator_host:
            os.environ.setdefault(
                "FIRESTORE_EMULATOR_HOST", settings.firestore_emulator_host
            )
        if settings.firebase_auth_emulator_host:
            os.environ.setdefault(
                "FIREBASE_AUTH_EMULATOR_HOST", settings.firebase_auth_emulator_host
            )
        if settings.storage_emulator_host:
            os.environ.setdefault(
                "STORAGE_EMULATOR_HOST", settings.storage_emulator_host
            )

        options = {
            "projectId": settings.firebase_project_id,
            "storageBucket": settings.firebase_storage_bucket,
        }

        if settings.google_application_credentials:
            cred = credentials.Certificate(settings.google_application_credentials)
        else:
            # Emulator / application-default creds. Anonymous works for emulators.
            try:
                cred = credentials.ApplicationDefault()
            except Exception:  # noqa: BLE001 — emulator has no ADC; that's fine
                cred = credentials.AnonymousCredentials()  # type: ignore[attr-defined]

        _app = firebase_admin.initialize_app(cred, options)
        logger.info(
            "Firebase initialised (project=%s, emulator=%s)",
            settings.firebase_project_id,
            bool(settings.firestore_emulator_host),
        )
        return _app


def db() -> FirestoreClient:
    """Return the Firestore client, initialising Firebase if needed."""
    init_firebase()
    return firestore.client()


# ── Path helpers (single source of truth for the document layout) ─────────────


def user_doc(uid: str) -> DocumentReference:
    return db().collection("users").document(uid)


def sites_col(uid: str) -> CollectionReference:
    return user_doc(uid).collection("sites")


def site_doc(uid: str, site_id: str) -> DocumentReference:
    return sites_col(uid).document(site_id)


def runs_col(uid: str, site_id: str) -> CollectionReference:
    return site_doc(uid, site_id).collection("runs")


def run_doc(uid: str, site_id: str, run_id: str) -> DocumentReference:
    return runs_col(uid, site_id).document(run_id)


def checkpoints_col() -> CollectionReference:
    return db().collection("checkpoints")


def all_sites():
    """Yield (uid, site_id, data) for every site across all users.

    Uses a Firestore collection-group query so the scheduler can scan every
    user's sites in one pass.
    """
    for snap in db().collection_group("sites").stream():
        parent = snap.reference.parent.parent  # users/{uid}
        uid = parent.id if parent else None
        yield uid, snap.id, (snap.to_dict() or {})
