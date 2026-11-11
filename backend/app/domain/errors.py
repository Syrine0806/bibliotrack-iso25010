"""Erreurs métier : chaque violation porte le code de la règle (traçabilité RG-xx)."""


class BusinessRuleError(Exception):
    """Violation d'une règle métier → HTTP 409 (conflit avec l'état courant)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class InvalidTransitionError(BusinessRuleError):
    """Transition de statut interdite par le workflow."""

    def __init__(self, entity: str, current: str, target: str) -> None:
        super().__init__(
            "WF-TRANSITION",
            f"Transition interdite pour {entity} : {current} → {target}",
        )
        self.current = current
        self.target = target


class PermissionDeniedError(Exception):
    """Action interdite pour le rôle / la propriété de la ressource → HTTP 403."""


class NotFoundError(Exception):
    def __init__(self, entity: str, entity_id: object) -> None:
        super().__init__(f"{entity} introuvable (id={entity_id})")
        self.entity = entity
        self.entity_id = entity_id
