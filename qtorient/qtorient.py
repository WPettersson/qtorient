#!/usr/bin/env python3


from glob import glob
import logging
import os
from subprocess import check_call, check_output, Popen
import sys

from PyQt5.QtCore import pyqtSlot, QObject, QTimer
from PyQt5.QtDBus import QDBusAbstractAdaptor, QDBusConnection
from PyQt5.QtWidgets import QSystemTrayIcon, QApplication, QMenu, QAction
from PyQt5.QtGui import QIcon

from qtorient.settings import OrientSettings

# decide which messages to show
LOG_LEVEL = logging.WARNING
# log output to a file (set to None to use stdout)
LOG_FILE = None
# the name of the display to rotate (None for default/everything)
OUTPUT = 'eDP1'
# which keyboards to disable when in tablet mode
KEYBOARDS = ('AT Translated Set 2 keyboard',)
# which pointing devices to disable when in tablet mode
POINTERS = ('TPPS/2 IBM TrackPoint', 'Synaptics TM2911-002')
# touchscreens that require rotation when screen is rotated
TOUCHSCREENS = ('ELAN Touchscreen', 'Wacom ISDv4 EC Pen stylus')
# how frequently to check sensor values for changes (in seconds)
POLL_INTERVAL = 1
# sensitivity to rotation (lower values = more sensitive)
GRAVITY_THRESHOLD = 2.0  # gravity trigger
# path to the various iio sensor directories
SENSORS_PATH = '/sys/bus/iio/devices/iio:device*'
# path to the lid switch sensor
LID_SENSOR_PATH = '/proc/acpi/button/lid/LID0/state'
# command to launch on-screen keyboard (in array form for Popen())
KEYBOARD_CMD = []
# how many errors in a row will cause this daemon to give up and exit
ERROR_TOLERANCE = 8

ORIENTATIONS = {
    'normal': {
        'pen': 'none',
        'transform_matrix': [1, 0, 0, 0, 1, 0, 0, 0, 1],
    },
    'inverted': {
        'pen': 'half',
        'transform_matrix': [-1, 0, 1, 0, -1, 1, 0, 0, 1],
    },
    'left': {
        'pen': 'ccw',
        'transform_matrix': [0, -1, 1, 1, 0, 0, 0, 0, 1],
    },
    'right': {
        'pen': 'cw',
        'transform_matrix': [0, 1, 0, -1, 0, 1, 0, 0, 1],
    },
}


class CoreApp(QApplication):
    """A subclass of QCoreApplication forces the python interpreter to run,
    which lets the signal handler run.
    """
    def __init__(self,
                 args,
                 output=OUTPUT,
                 keyboards=KEYBOARDS,
                 pointers=POINTERS,
                 touchscreens=TOUCHSCREENS):
        super().__init__(args)
        self._settings = None
        self._laptop = None
        self._input_devices = None
        # Logging
        logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL)
        # access to env (for making external calls)
        self.env = os.environ.copy()
        # access to various parameters
        self.output = output
        # weed out any input devices that aren't actually available
        self.keyboards = self.verify_input_devices(keyboards)
        self.pointers = self.verify_input_devices(pointers)
        self.touchscreens = self.verify_input_devices(touchscreens)
        self.accel_base_dir = None
        self.incl_base_dir = None
        # After suspending, we might be resetting the USB device, so we allow a
        # small number of consecutive failures
        self._read_fails = 0
        self._read_fails_max = 100
        self.keyboard_pid = None
        self.orientation = 'normal'
        self._accel = [0, 0]
        self._incl = [0, 0, 0]
        interface = "se.ewpettersson.yoga"
        path = "/se/ewpettersson/yoga"
        method = "tabletmode"
        self.bus = QDBusConnection.systemBus()
        # signal is sent by dbus-send so empty service
        self.bus.connect('', path, interface, method, 'b', self.check_mode)
        self._tray = QSystemTrayIcon(QIcon.fromTheme("input-tablet"), self)
        self._tray.show()
        self._tray.activated.connect(self.systray_clicked)
        self.make_menu()
        # Don't quit when settings window is closed
        self.setQuitOnLastWindowClosed(False)
        # Run event loop every POLL_INTERVAL seconds
        self.startTimer(POLL_INTERVAL * 1000)

    def systray_clicked(self, reason):
        """Ignore context menu clicks (the menu pops up anyway as a context
        menu is registered), otherwise show/hide settings.
        """
        if reason == QSystemTrayIcon.Context:
            return
        self.toggle_settings()

    def make_menu(self):
        """Make the systray menu.
        """
        self._menu = QMenu()
        self._quit_action = QAction("Quit")
        self._quit_action.triggered.connect(self.stop)
        self._settings_action = QAction("Settings")
        self._settings_action.triggered.connect(self.toggle_settings)
        self._menu.addAction(self._settings_action)
        self._menu.addAction(self._quit_action)
        self._tray.setContextMenu(self._menu)

    def toggle_settings(self):
        """Show the settings dialog."""
        if self._settings is not None:
            self._settings.close()
            self._settings = None
        else:
            self._settings = OrientSettings(self)
            self._settings.set_incl(self._incl)
            self._settings.set_accel(self._accel)

    @property
    def is_laptop(self):
        """Are we in laptop mode (True) or tablet mode (False)
        """
        # If we know for sure (i.e. ACPI events) then return those
        if self._laptop is True:
            return True
        if self._laptop is False:
            return False
        x, y = self._incl[0:2]
        # Always assume laptop mode if lid is closed, probably docked
        # TODO Configuration option for the below magic numbers
        if not self.is_lid_open() or ((-15 < x < 1) and (-5 < y < 4)):
            return True
        return False

    def is_lid_open(self):
        """Is the lid open?
        """
        def is_lid_open(self):
            with open(LID_SENSOR_PATH) as f:
                return 'open' in f.read()

    @pyqtSlot(bool)
    def check_mode(self, is_tablet):
        is_laptop = not is_tablet
        if is_laptop != self._laptop:
            self._laptop = is_laptop
            self.set_mode(self._laptop)

    def _get_sensor_base_dirs(self):
        for path in glob(SENSORS_PATH):
            with open(os.path.join(path, 'name')) as device:
                name = device.read()
                if 'accel' in name:
                    self.accel_base_dir = path
                elif 'incli' in name:
                    self.incl_base_dir = path
            if self.accel_base_dir and self.incl_base_dir:
                break
        else:
            sys.stderr.write("Cannot find all sensor devices\n")
            sys.exit(1)

    def stop(self, *args, **kwargs):
        logging.info('Signal Received: exiting cleanly')
        # revert back to laptop mode and restore all functionality
        if not self.is_laptop:
            self._laptop = True
            self.set_mode(self._laptop)
        # revert back to normal orientation
        if self.orientation != 'normal':
            self.orientation = 'normal'
            self.set_orientation(self.orientation)
        # kill on-screen keyboard if it's still running
        self.kill_keyboard()
        self.quit()

    @property
    def input_devices(self):
        if self._input_devices is None:
            # use xinput to create a list of all available input devices
            cmd = ['xinput', '--list', '--name-only']
            devices = check_output(cmd, env=self.env).splitlines()
            # conver to set so that we can easily compare collections
            self._input_devices = set(d.decode("UTF-8") for d in devices)
        return self._input_devices

    def verify_input_devices(self, devices):
        return tuple(set(devices) & self.input_devices)

    def read_sensor(self, base_dir, fname):
        """Read a sensor file. Note that after suspending, we might be
        resetting the USB device, so we allow a small number of consecutive
        failures
        """
        try:
            with open(os.path.join(base_dir, fname), 'r') as device:
                self._read_fails = 0
                return float(device.read())
        except FileNotFoundError as exception:
            self._read_fails += 1
            if self._read_fails > self._read_fails_max:
                raise exception
            return 0.0
        except Exception as exception:
            raise exception

    def read_incl(self):
        if not self.incl_base_dir:
            self._get_sensor_base_dirs()
        base_dir = self.incl_base_dir
        # multiply by 10 for better granularity
        scale = self.read_sensor(base_dir, 'in_incli_scale') * 10
        self._incl = [self.read_sensor(base_dir, 'in_incli_x_raw') * scale,
                      self.read_sensor(base_dir, 'in_incli_y_raw') * scale,
                      self.read_sensor(base_dir, 'in_incli_z_raw') * scale]
        if self._settings:
            self._settings.set_incl(self._incl)

    def read_accel(self):
        if not self.accel_base_dir:
            self._get_sensor_base_dirs()
        base_dir = self.accel_base_dir
        scale = self.read_sensor(base_dir, 'in_accel_scale')
        self._accel = [self.read_sensor(base_dir, 'in_accel_x_raw') * scale,
                       self.read_sensor(base_dir, 'in_accel_y_raw') * scale]
        if self._settings:
            self._settings.set_accel(self._accel)

    def rotate_screen(self, orientation):
        os.system('xrandr --output %s --rotate %s' % (self.output,
                                                      orientation))

    def set_mode(self, is_laptop):
        """
        i.e. laptop or tablet
        """
        logging.info('set mode: %s', 'laptop' if is_laptop else 'tablet')
        func = 'enable' if is_laptop else 'disable'
        # disable keyboard and pointers (other than touchscreen)
        for keyboard in self.keyboards:
            check_call(['xinput', func, 'keyboard:%s' % keyboard],
                       env=self.env)
        for pointer in self.pointers:
            check_call(['xinput', func, 'pointer:%s' % pointer], env=self.env)
        # show/hide onscreen keyboard
        if not is_laptop:
            self.launch_keyboard()
        else:
            self.kill_keyboard()

    def get_orientation(self):
        x, y = self._accel
        # use the axis with the highest offset
        if abs(x) > abs(y):
            if x <= -GRAVITY_THRESHOLD:
                return 'right'
            if x >= GRAVITY_THRESHOLD:
                return 'left'
        else:
            if y <= -GRAVITY_THRESHOLD:
                return 'normal'
            if y >= GRAVITY_THRESHOLD:
                return 'inverted'
        # if thresholds not exceeded, stay where we are
        return self.orientation

    def set_orientation(self, orientation):
        logging.info("set orientation: %s", orientation)
        # rotate the screen
        check_call(['xrandr', '--output', self.output, '--rotate',
                    orientation], env=self.env)
        # set tranformation matrix coords for the touchscreen(s) (i.e. rotate)
        matrix = ORIENTATIONS[orientation]['transform_matrix']
        for touchscreen in self.touchscreens:
            check_call(['xinput', 'set-prop', touchscreen,
                        'Coordinate Transformation Matrix', ] +
                       [str(n) for n in matrix],
                       env=self.env)

    def launch_keyboard(self):
        if not KEYBOARD_CMD:
            return None
        if self.keyboard_pid is None:
            self.keyboard_pid = Popen(KEYBOARD_CMD, env=self.env).pid
        return self.keyboard_pid

    def kill_keyboard(self):
        if self.keyboard_pid:
            os.system('kill %s' % self.keyboard_pid)
            self.keyboard_pid = None

    def event(self, e):
        """Force events to run in python interpreter, which lets signal handler run
        """
        self.read_incl()
        self.read_accel()
        logging.debug("[State: %s] "
                      "[Incl X: % 6.2f, Y: % 6.2f, Z: % 6.2f] "
                      "[Accel X: % 6.2f, Y: % 6.2f]",
                      "laptop" if self.is_laptop else "tablet",
                      *(self._incl + self._accel))
        orientation = 'normal'
        if not self.is_laptop:
            orientation = self.get_orientation()
        if orientation != self.orientation:
            self.orientation = orientation
            self.set_orientation(self.orientation)
        return QApplication.event(self, e)

