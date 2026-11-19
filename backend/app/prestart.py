"""Initialisation exécutée UNE fois avant le démarrage des workers (conteneur).

Fiabilité : attend que la base soit joignable (reprises avec temporisation croissante),
puis crée le schéma, charge les données de démo si demandé et lance la maintenance.
"""

import logging
import sys
import time

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import engine
from app.main import init_database

log = logging.getLogger("biblio.prestart")


def wait_for_database(attempts: int = 30, delay: float = 1.0) -> None:
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("Base de données joignable (tentative %d)", attempt)
            return
        except OperationalError:
            log.warning("Base indisponible (tentative %d/%d), nouvel essai…", attempt, attempts)
            time.sleep(min(delay * attempt, 5))
    log.error("Base de données injoignable : abandon.")
    sys.exit(1)


if __name__ == "__main__":
    wait_for_database()
    init_database()
    log.info("Initialisation terminée.")
