import os
from logging import debug, warning, error
from typing import Dict, Type, Any
from urllib import request

from yamlable import yaml_info, Y

from linguard.common.properties import global_properties
from linguard.common.utils.network import get_default_gateway
from linguard.common.utils.system import Command
from linguard.core.config.base import BaseConfig


@yaml_info(yaml_tag='wireguard')
class WireguardConfig(BaseConfig):
    __IP_RETRIEVER_URL = "https://api.ipify.org"
    INTERFACES_FOLDER_NAME = "interfaces"

    endpoint: str
    wg_bin: str
    wg_quick_bin: str
    iptables_bin: str

    @property
    def interfaces_folder(self):
        return global_properties.join_workdir(self.INTERFACES_FOLDER_NAME)

    def __init__(self):
        self.load_defaults()

    def load_defaults(self):
        self.endpoint = ""
        self.iptables_bin = ""
        self.wg_bin = ""
        self.wg_quick_bin = ""
        result = Command("whereis wg | tr ' ' '\n' | grep bin").run()
        if result.successful:
            self.wg_bin = result.output
        result = Command("whereis wg-quick | tr ' ' '\n' | grep bin").run()
        if result.successful:
            self.wg_quick_bin = result.output
        result = Command("whereis iptables | tr ' ' '\n' | grep bin").run()
        if result.successful:
            self.iptables_bin = result.output
        from linguard.core.models import interfaces
        self.interfaces = interfaces

    def load(self, config: "WireguardConfig"):
        self.endpoint = config.endpoint or self.endpoint
        if not self.endpoint:
            warning("No endpoint specified. Retrieving public IP address...")
            self.set_default_endpoint()
        self.wg_bin = config.wg_bin or self.wg_bin
        self.wg_quick_bin = config.wg_quick_bin or self.wg_quick_bin
        self.iptables_bin = config.iptables_bin or self.iptables_bin
        if config.interfaces:
            self.interfaces.set_contents(config.interfaces)
        for iface in self.interfaces.values():
            iface.conf_file = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            iface.save()

    def set_default_endpoint(self):
        try:
            self.endpoint = request.urlopen(self.__IP_RETRIEVER_URL).read().decode("utf-8")
            debug(f"Public IP address is {self.endpoint}. This will be used as default endpoint.")
        except Exception as e:
            error(f"Unable to obtain server's public IP address: {e}")
            ip = (Command(f"ip a show {get_default_gateway()} | grep inet | head -n1 | xargs | cut -d ' ' -f2")
                  .run().output)
            self.endpoint = ip.split("/")[0]
            if not self.endpoint:
                error("Unable to automatically set endpoint.")
                return
            warning(f"Server endpoint set to {self.endpoint}: this might not be a public IP address!")

    @classmethod
    def __from_yaml_dict__(cls,  # type: Type[Y]
                           dct,  # type: Dict[str, Any]
                           yaml_tag=""
                           ):  # type: (...) -> Y
        config = WireguardConfig()
        config.endpoint = dct.get("endpoint", None) or config.endpoint
        config.wg_bin = dct.get("wg_bin", None) or config.wg_bin
        config.wg_quick_bin = dct.get("wg_quick_bin", None) or config.wg_quick_bin
        config.iptables_bin = dct.get("iptables_bin", None) or config.iptables_bin
        config.interfaces = dct.get("interfaces", None) or config.interfaces
        for iface in config.interfaces.values():
            iface.conf_file = os.path.join(config.interfaces_folder, iface.name) + ".conf"
            iface.save()
        return config

    def __to_yaml_dict__(self):  # type: (...) -> Dict[str, Any]
        return {
            "endpoint": self.endpoint,
            "wg_bin": self.wg_bin,
            "wg_quick_bin": self.wg_quick_bin,
            "iptables_bin": self.iptables_bin,
            "interfaces": self.interfaces
        }

    def apply(self):
        super(WireguardConfig, self).apply()
        for iface in self.interfaces.values():
            was_up = iface.is_up
            iface.down()
            if os.path.exists(iface.conf_file):
                os.remove(iface.conf_file)
            iface.conf_file = os.path.join(self.interfaces_folder, iface.name) + ".conf"
            if was_up:
                iface.up()


config = WireguardConfig()
