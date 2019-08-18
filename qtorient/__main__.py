"""Run the app."""

import signal
import sys

from qtorient.qtorient import CoreApp


def main():
    """Run the app"""
    app = CoreApp(sys.argv)
    signal.signal(signal.SIGINT, lambda *a: app.stop())
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
