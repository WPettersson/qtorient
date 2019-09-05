from PyQt5.QtWidgets import QWidget

from qtorient.Ui_qtorient import Ui_qtorient


class OrientSettings(QWidget):
    """A window showing some settings, and some status information.
    """
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.ui = Ui_qtorient()
        self.ui.setupUi(self)
        self.ui.buttonBox.clicked.connect(self.buttonPress)
        self.ui.pollEdit.setText(f"{self.parent.poll_interval}")
        self.setup_dropdowns()
        self.show()

    def setup_dropdowns(self):
        """Add entries to dropdowns for mode and orientation."""
        for mode in ["Laptop (auto)", "Tablet (auto)"]:
            self.ui.modeBox.addItem(mode)
        for orient in ["Normal (auto)", "Left (auto)", "Right (auto)",
                       "Invert (auto)"]:
            self.ui.orientBox.addItem(orient)

    def buttonPress(self, button):
        """A button is pressed in the button box
        :param button: the button pressed, irrelevant at the moment since there
        is only one button."""
        try:
            poll_interval = int(self.ui.pollEdit.text())
            if poll_interval > 0:
                self.parent.poll_interval = poll_interval
        except ValueError:
            # Ignore if not integer
            pass
        self.parent.toggle_settings()

    def set_accel(self, accel):
        """Set the acceleration values in the GUI.
        :param accel: a triple (x,y,z) of floats of the acceleration
        """
        self.ui.accel_x.setText(f"{accel[0]:.2f}")
        self.ui.accel_y.setText(f"{accel[1]:.2f}")

    def set_incl(self, incl):
        """Set the inclination values in the GUI.
        :param incl: a triple (x,y,z) of floats of the inclination
        """
        self.ui.incl_x.setText(f"{incl[0]:.2f}")
        self.ui.incl_y.setText(f"{incl[1]:.2f}")
        self.ui.incl_z.setText(f"{incl[2]:.2f}")

    def set_mode(self, is_laptop, is_auto=True):
        """Set the mode of the device (laptop/tablet).
        :param is_laptop: True if we are switching to laptop mode, False
        otherwise.
        :param is_auto: True if this is an autodetected change, False if it is
        user controlled
        """
        if is_laptop and is_auto:
            self.ui.modeBox.setCurrentText("Laptop (auto)")
        elif not is_laptop and is_auto:
            self.ui.modeBox.setCurrentText("Tablet (auto)")

    def set_orientation(self, orientation, is_auto=True):
        """Set the orientation of the device.
        :param orientation: A string, one of "normal", "inverted", "left", or
        "right"
        :param is_auto: True if this is an autodetected change, False if it is
        user controlled
        """
        if is_auto:
            if orientation == "normal":
                self.ui.orientBox.setCurrentText("Normal (auto)")
            elif orientation == "left":
                self.ui.orientBox.setCurrentText("Left (auto)")
            elif orientation == "right":
                self.ui.orientBox.setCurrentText("Right (auto)")
            elif orientation == "inverted":
                self.ui.orientBox.setCurrentText("Inverted (auto)")
