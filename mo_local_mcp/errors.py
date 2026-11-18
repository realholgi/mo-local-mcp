"""Gezielte Fehlerarten für stabile MCP-Fehlercodes, weiterhin ValueError-kompatibel."""


class ParameterFehler(ValueError):
    """Ein ausdrücklich geprüfter Aufrufparameter ist ungültig."""


class RechteFehler(ValueError):
    """Die Startrechte erlauben diesen Zugriff nicht."""


class DatenstandGeaendert(ValueError):
    """Der geöffnete Datenbankstand ist nicht mehr unverändert und ruhend."""


class Abfragegrenze(ValueError):
    """Eine Abfrage überschreitet eine festgelegte Ressourcen- oder Ausgabegrenze."""


class DatenFehler(ValueError):
    """Gespeicherte Daten verletzen eine ausdrücklich geprüfte Fachbedingung."""
