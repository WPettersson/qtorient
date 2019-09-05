from PyQt5.QtWidgets import QWidget

from qtorient.Ui_qtorient import Ui_qtorient


class OrientSettings(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.ui = Ui_qtorient()
        self.ui.setupUi(self)
        self.ui.buttonBox.clicked.connect(self.buttonPress)
        self.ui.pollEdit.setText(f"{self.parent.poll_interval}")
        self.show()

    def buttonPress(self, button):
        """A button is pressed in the button box."""
        try:
            poll_interval = int(self.ui.pollEdit.text())
            if poll_interval > 0:
                self.parent.poll_interval = poll_interval
        except ValueError:
            # Ignore if not integer
            pass
        self.parent.toggle_settings()

    def set_accel(self, accel):
        """Set the inclination values in the GUI.
        """
        self.ui.accel_x.setText(f"{accel[0]:.2f}")
        self.ui.accel_y.setText(f"{accel[1]:.2f}")

    def set_incl(self, incl):
        """Set the inclination values in the GUI.
        """
        self.ui.incl_x.setText(f"{incl[0]:.2f}")
        self.ui.incl_y.setText(f"{incl[1]:.2f}")
        self.ui.incl_z.setText(f"{incl[2]:.2f}")

