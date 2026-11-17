"""Gemeinsame deutsche Hilfe für die beiden Kommandozeilenprogramme."""

import argparse
import sys


class DeutscherArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, add_help=False, **kwargs)
        self._positionals.title = 'Argumente'
        self._optionals.title = 'Optionen'
        self.add_argument('-h', '--hilfe', action='help', help='Diese Hilfe anzeigen und beenden')

    def format_usage(self):
        return super().format_usage().replace('usage:', 'Aufruf:', 1)

    def format_help(self):
        return super().format_help().replace('usage:', 'Aufruf:', 1)

    def error(self, message):
        for englisch, deutsch in (
            ('the following arguments are required:', 'Erforderliche Argumente fehlen:'),
            ('unrecognized arguments:', 'Unbekannte Argumente:'),
            ('expected one argument', 'ein Wert wird erwartet'),
            ('ignored explicit argument', 'unerwarteter Wert'),
            ('argument ', 'Argument '),
        ):
            message = message.replace(englisch, deutsch)
        self.print_usage(sys.stderr)
        self.exit(2, f'{self.prog}: Fehler: {message}\n')
