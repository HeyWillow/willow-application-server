from logging import getLogger

from app.db.main import get_config_db
from app.internal.command_endpoints.ha_ws import (
    HomeAssistantWebSocketEndpoint,
)
from app.internal.command_endpoints.mqtt import MqttConfig, MqttEndpoint
from app.internal.command_endpoints.openhab import OpenhabEndpoint
from app.internal.command_endpoints.rest import RestEndpoint


log = getLogger("WAS")


def init_command_endpoint(app):
    # call command_endpoint.stop() to avoid leaking asyncio task
    try:
        app.command_endpoint.stop()
    except Exception:
        pass

    user_config = get_config_db()

    if "was_mode" in user_config and user_config["was_mode"]:
        log.info("WAS Endpoint mode enabled")

        if user_config["command_endpoint"] == "Home Assistant":

            host = user_config["hass_host"]
            port = user_config["hass_port"]
            tls = user_config["hass_tls"]
            token = user_config["hass_token"]

            app.command_endpoint = HomeAssistantWebSocketEndpoint(app, host, port, tls, token)

        elif user_config["command_endpoint"] == "MQTT":
            mqtt_config = MqttConfig()
            mqtt_config.set_auth_type(user_config["mqtt_auth_type"])
            mqtt_config.set_hostname(user_config["mqtt_host"])
            mqtt_config.set_port(user_config["mqtt_port"])
            mqtt_config.set_tls(user_config["mqtt_tls"])
            mqtt_config.set_topic(user_config["mqtt_topic"])

            if 'mqtt_password' in user_config:
                mqtt_config.set_password(user_config['mqtt_password'])

            if 'mqtt_username' in user_config:
                mqtt_config.set_username(user_config['mqtt_username'])

            app.command_endpoint = MqttEndpoint(mqtt_config)

        elif user_config["command_endpoint"] == "openHAB":
            app.command_endpoint = OpenhabEndpoint(user_config["openhab_url"], user_config["openhab_token"])

        elif user_config["command_endpoint"] == "REST":
            app.command_endpoint = RestEndpoint(user_config["rest_url"])

            if hasattr(user_config, "rest_auth_type"):
                app.command_endpoint.config.set_auth_type(user_config["rest_auth_type"])

            if "rest_auth_header" in user_config:
                app.command_endpoint.config.set_auth_header(user_config["rest_auth_header"])

            if "rest_auth_pass" in user_config:
                app.command_endpoint.config.set_auth_pass(user_config["rest_auth_pass"])

            if "rest_auth_user" in user_config:
                app.command_endpoint.config.set_auth_user(user_config["rest_auth_user"])
