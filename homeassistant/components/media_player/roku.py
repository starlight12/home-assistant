"""
Support for the Roku media player.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.roku/
"""
import logging


from homeassistant.components.roku import (DATA_ENTITIES)
from homeassistant.components.media_player import (
    MEDIA_TYPE_MOVIE, SUPPORT_NEXT_TRACK, SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_PLAY, MediaPlayerDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, STATE_IDLE, STATE_PLAYING, STATE_UNKNOWN,
    STATE_HOME)

REQUIREMENTS = ['python-roku==3.1.5']

DEPENDENCIES = ['roku']

DEFAULT_PORT = 8060

_LOGGER = logging.getLogger(__name__)

SUPPORT_ROKU = SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK |\
    SUPPORT_PLAY_MEDIA | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |\
    SUPPORT_SELECT_SOURCE | SUPPORT_PLAY


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Roku platform."""
    if not discovery_info:
        return

    # Manage entity cache for service handler
    if DATA_ENTITIES not in hass.data:
        hass.data[DATA_ENTITIES] = []

    name = discovery_info[CONF_NAME]
    host = discovery_info[CONF_HOST]
    entity = RokuDevice(host, name)

    if entity not in hass.data[DATA_ENTITIES]:
        hass.data[DATA_ENTITIES].append(entity)

    add_devices([entity])


class RokuDevice(MediaPlayerDevice):
    """Representation of a Roku device on the network."""

    def __init__(self, host, name):
        """Initialize the Roku device."""
        from roku import Roku

        self.roku = Roku(host)
        self.ip_address = host
        self.channels = []
        self.current_app = None
        self.device_info = {}
        self.devname = name
        self.update()

    def update(self):
        """Retrieve latest state."""
        import requests.exceptions

        try:
            self.device_info = self.roku.device_info
            self.ip_address = self.roku.host
            self.channels = self.get_source_list()

            if self.roku.current_app is not None:
                self.current_app = self.roku.current_app
            else:
                self.current_app = None
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout):

            pass

    def get_source_list(self):
        """Get the list of applications to be used as sources."""
        return ["Home"] + sorted(channel.name for channel in self.roku.apps)

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self.devname

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self.device_info.sernum

    @property
    def state(self):
        """Return the state of the device."""
        if self.current_app is None:
            return STATE_UNKNOWN

        if (self.current_app.name == "Power Saver" or
                self.current_app.is_screensaver):
            return STATE_IDLE
        elif self.current_app.name == "Roku":
            return STATE_HOME
        elif self.current_app.name is not None:
            return STATE_PLAYING

        return STATE_UNKNOWN

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ROKU

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self.device_info.sernum

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        if self.current_app is None:
            return None
        elif self.current_app.name == "Power Saver":
            return None
        elif self.current_app.name == "Roku":
            return None
        return MEDIA_TYPE_MOVIE

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if self.current_app is None:
            return None
        elif self.current_app.name == "Roku":
            return None
        elif self.current_app.name == "Power Saver":
            return None
        elif self.current_app.id is None:
            return None

        return 'http://{0}:{1}/query/icon/{2}'.format(
            self.ip_address, DEFAULT_PORT, self.current_app.id)

    @property
    def app_name(self):
        """Name of the current running app."""
        if self.current_app is not None:
            return self.current_app.name

    @property
    def app_id(self):
        """Return the ID of the current running app."""
        if self.current_app is not None:
            return self.current_app.id

    @property
    def source(self):
        """Return the current input source."""
        if self.current_app is not None:
            return self.current_app.name

    @property
    def source_list(self):
        """List of available input sources."""
        return self.channels

    @property
    def is_on(self):
        """Return true if device is on."""
        return True

    def media_play_pause(self):
        """Send play/pause command."""
        if self.current_app is not None:
            self.roku.play()

    def media_previous_track(self):
        """Send previous track command."""
        if self.current_app is not None:
            self.roku.reverse()

    def media_next_track(self):
        """Send next track command."""
        if self.current_app is not None:
            self.roku.forward()

    def mute_volume(self, mute):
        """Mute the volume."""
        if self.current_app is not None:
            self.roku.volume_mute()

    def volume_up(self):
        """Volume up media player."""
        if self.current_app is not None:
            self.roku.volume_up()

    def volume_down(self):
        """Volume down media player."""
        if self.current_app is not None:
            self.roku.volume_down()

    def select_source(self, source):
        """Select input source."""
        if self.current_app is not None:
            if source == "Home":
                self.roku.home()
            else:
                channel = self.roku[source]
                channel.launch()
