"""Support for DD-WRT routers."""
import logging
import re

import requests
import voluptuous as vol

from homeassistant.components.device_tracker import (
    DOMAIN, PLATFORM_SCHEMA, DeviceScanner)
from homeassistant.const import (
    CONF_HOST, CONF_HOSTS, CONF_PASSWORD, CONF_SSL, CONF_USERNAME,
    CONF_VERIFY_SSL)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

_DDWRT_DATA_REGEX = re.compile(r'\{(\w+)::([^\}]*)\}')
_MAC_REGEX = re.compile(r'(([0-9A-Fa-f]{1,2}\:){5}[0-9A-Fa-f]{1,2})')

DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
HOST_GROUP = 'Single host or list of hosts'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Exclusive(CONF_HOST, HOST_GROUP): cv.string,
    vol.Exclusive(CONF_HOSTS, HOST_GROUP): cv.ensure_list,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
})


def get_scanner(hass, config):
    """Validate the configuration and return a DD-WRT scanner."""
    try:
        return DdWrtDeviceScanner(config[DOMAIN])
    except ConnectionError:
        return None


class DdWrtDeviceScanner(DeviceScanner):
    """This class queries a wireless router running DD-WRT firmware."""

    def __init__(self, config):
        """Initialize the DD-WRT scanner."""
        self.protocol = 'https' if config[CONF_SSL] else 'http'
        self.verify_ssl = config[CONF_VERIFY_SSL]
        self.host = config.get(CONF_HOST)
        if not self.host:
            self.host = config.get(CONF_HOSTS, [])
        else:
            self.host = [self.host]
        _LOGGER.debug("Hosts %s", self.host)

        self.username = config[CONF_USERNAME]
        self.password = config[CONF_PASSWORD]

        self.last_results = {}
        self.mac2name = {}

        # Test the router is accessible
        data = {}
        for host in self.host:
            url = '{}://{}/Status_Wireless.live.asp'.format(
                self.protocol, host)
            data[host] = self.get_ddwrt_data(url)
            _LOGGER.debug("Updating %s: %s", host, data[host])
            if not data[host]:
                raise ConnectionError('Cannot connect to router: {}'.format
                                      (host))

    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return self.last_results

    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        # If not initialised and not already scanned and not found.
        data = {}
        self.mac2name = {}
        if device not in self.mac2name:
            for host in self.host:
                url = '{}://{}/Status_Wireless.live.asp'.format(
                    self.protocol, host)
                data[host] = self.get_ddwrt_data(url)
                _LOGGER.debug("Updating %s: %s", host, data[host])

                if not data[host]:
                    continue

                dhcp_leases = data[host].get('dhcp_leases', None)

                if not dhcp_leases:
                    continue

                # Remove leading and trailing quotes and spaces
                cleaned_str = dhcp_leases.replace(
                    "\"", "").replace("\'", "").replace(" ", "")
                elements = cleaned_str.split(',')
                num_clients = int(len(elements) / 5)
                for idx in range(0, num_clients):
                    # The data is a single array
                    # every 5 elements represents one host, the MAC
                    # is the third element and the name is the first.
                    mac_index = (idx * 5) + 2
                    if mac_index < len(elements):
                        mac = elements[mac_index]
                        self.mac2name[mac] = elements[idx * 5]

        return self.mac2name.get(device)

    def _update_info(self):
        """Ensure the information from the DD-WRT router is up to date.

        Return boolean if scanning successful.
        """
        _LOGGER.info("Checking ARP")

        data = {}
        self.last_results = []

        for host in self.host:
            url = '{}://{}/Status_Wireless.live.asp'.format(
                self.protocol, host)
            data[host] = self.get_ddwrt_data(url)
            _LOGGER.debug("Updating %s: %s", host, data[host])
            if not data[host]:
                continue

            active_clients = data[host].get('active_wireless', None)

            if not active_clients:
                continue

            # The DD-WRT UI uses its own data format and then
            # regex's out values so this is done here too
            # Remove leading and trailing single quotes.
            clean_str = active_clients.strip().strip("'")
            elements = clean_str.split("','")

            self.last_results.extend(item for item in elements
                                     if _MAC_REGEX.match(item))
        if self.last_results:
            _LOGGER.debug("Last results: %s", self.last_results)
            return True
        return False

    def get_ddwrt_data(self, url):
        """Retrieve data from DD-WRT and return parsed result."""
        try:
            response = requests.get(
                url, auth=(self.username, self.password),
                timeout=4, verify=self.verify_ssl)
        except requests.exceptions.Timeout:
            _LOGGER.exception("Connection to the router timed out")
            return
        if response.status_code == 200:
            return _parse_ddwrt_response(response.text)
        if response.status_code == 401:
            # Authentication error
            _LOGGER.exception(
                "Failed to authenticate, check your username and password")
            return
        _LOGGER.error("Invalid response from DD-WRT: %s", response)


def _parse_ddwrt_response(data_str):
    """Parse the DD-WRT data format."""
    return {
        key: val for key, val in _DDWRT_DATA_REGEX.findall(data_str)}
