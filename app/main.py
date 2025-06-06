import asyncio
import json
import os

import alembic
import alembic.config
from fastapi import (
    FastAPI,
    Header,
    WebSocket,
    WebSocketDisconnect,
)
from contextlib import asynccontextmanager
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import logging
from pathlib import Path
from shutil import move
from typing import Annotated
from websockets.exceptions import ConnectionClosed
from fastapi.middleware.cors import CORSMiddleware

from app.const import (
    ALEMBIC_CONFIG,
    DIR_OTA,
    STORAGE_USER_CLIENT_CONFIG,
    STORAGE_USER_CONFIG,
    STORAGE_USER_NVS,
)

from app.db.main import get_config_db, migrate_user_client_config, migrate_user_config, migrate_user_nvs
from app.internal.command_endpoints import (
    CommandEndpointResponse,
    CommandEndpointResult,
    CommandEndpointRuntimeException
)
from app.internal.command_endpoints.main import init_command_endpoint
from app.internal.was import (
    build_msg,
    get_config,
    get_devices,
    get_nvs,
    get_tz_config,
)
from app.settings import get_settings

from .internal.client import Client
from .internal.connmgr import ConnMgr
from .internal.notify import NotifyQueue
from .internal.wake import WakeEvent, WakeSession
from .routers import asset
from .routers import client
from .routers import config
from .routers import info
from .routers import ota
from .routers import release
from .routers import status


logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

log = logging.getLogger("WAS")
try:
    log.setLevel(os.environ.get("WAS_LOG_LEVEL").upper())
except Exception:
    pass

settings = get_settings()

def db_migrations():
    cfg = alembic.config.Config(ALEMBIC_CONFIG)
    cfg.attributes['logger'] = log
    alembic.command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # database schema migrations
    db_migrations()

    migrate_user_files()
    get_tz_config(refresh=True)

    user_config = get_config()
    # skip migration if user_config is empty
    if user_config:
        try:
            migrate_user_config(user_config)
            os.remove(STORAGE_USER_CONFIG)
        except Exception as e:
            log.error(f"failed to migrate user config to database: {e}")

    user_nvs = get_nvs()
    # skip migration if user_nvs is empty
    if user_nvs:
        try:
            migrate_user_nvs(user_nvs)
            os.remove(STORAGE_USER_NVS)
        except Exception as e:
            log.error(f"failed to migrate user nvs to database: {e}")

    devices = get_devices()
    # skip migration if devices is empty
    if devices:
        try:
            migrate_user_client_config(devices)
            os.remove(STORAGE_USER_CLIENT_CONFIG)
        except Exception as e:
            log.error(f"failed to migrate user client config to database: {e}")
    app.connmgr = ConnMgr()

    app.command_endpoint = None
    try:
        init_command_endpoint(app)
    except Exception as e:
        log.error(f"failed to initialize command endpoint ({e})")

    app.notify_queue = NotifyQueue(connmgr=app.connmgr)
    app.notify_queue.start()

    yield
    log.info("shutting down")

app = FastAPI(title="Willow Application Server",
              description="Willow Management API",
              openapi_url="/openapi.json",
              docs_url="/docs",
              lifespan=lifespan,
              redoc_url="/redoc",
              version=settings.was_version)

wake_session = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def migrate_user_files():
    for user_file in ['user_config.json', 'user_multinet.json', 'user_nvs.json']:
        if os.path.isfile(user_file):
            dest = f"storage/{user_file}"
            if not os.path.isfile(dest):
                move(user_file, dest)


def hex_mac(mac):
    if isinstance(mac, list):
        mac = '%02x:%02x:%02x:%02x:%02x:%02x' % (mac[0], mac[1], mac[2], mac[3], mac[4], mac[5])
    return mac


# Make sure we always have DIR_OTA
Path(DIR_OTA).mkdir(parents=True, exist_ok=True)


app.mount("/admin", StaticFiles(directory="static/admin", html=True), name="admin")


@app.get("/", response_class=RedirectResponse)
def api_redirect_admin():
    log.debug('API GET ROOT: Request')
    return "/admin"


app.include_router(asset.router)
app.include_router(client.router)
app.include_router(config.router)
app.include_router(info.router)
app.include_router(ota.router)
app.include_router(release.router)
app.include_router(status.router)


# WebSockets with params return 403 when done with APIRouter
# https://github.com/tiangolo/fastapi/issues/98#issuecomment-1688632239
@app.websocket("/ws")
async def websocket_endpoint(
        websocket: WebSocket,
        user_agent: Annotated[str | None, Header(convert_underscores=True)] = None):
    client = Client(ua=user_agent)

    await app.connmgr.accept(websocket, client)
    try:
        while True:
            data = await websocket.receive_text()
            log.debug(str(data))
            msg = json.loads(data)

            # latency sensitive so handle first
            if "wake_start" in msg:
                global wake_session
                if wake_session is not None:
                    if wake_session.done:
                        del wake_session
                        wake_session = WakeSession()
                        asyncio.create_task(wake_session.cleanup())
                else:
                    wake_session = WakeSession()
                    asyncio.create_task(wake_session.cleanup())

                if "wake_volume" in msg["wake_start"]:
                    wake_event = WakeEvent(websocket, msg["wake_start"]["wake_volume"])
                    wake_session.add_event(wake_event)

            elif "wake_end" in msg:
                pass

            elif "notify_done" in msg:
                app.notify_queue.done(websocket, msg["notify_done"])

            elif "cmd" in msg:
                if msg["cmd"] == "endpoint":
                    if app.command_endpoint is not None:
                        log.debug(f"Sending {msg['data']} to {app.command_endpoint.name}")
                        try:
                            resp = app.command_endpoint.send(jsondata=msg["data"], ws=websocket, client=client)
                            if resp is not None:
                                resp = app.command_endpoint.parse_response(resp)
                                log.debug(f"Got response {resp} from endpoint")
                                # HomeAssistantWebSocketEndpoint sends message via callback
                                if resp is not None:
                                    asyncio.ensure_future(websocket.send_text(resp))
                        except CommandEndpointRuntimeException as e:
                            command_endpoint_result = CommandEndpointResult(speech="WAS Command Endpoint unreachable")
                            command_endpoint_response = CommandEndpointResponse(result=command_endpoint_result)
                            asyncio.ensure_future(websocket.send_text(command_endpoint_response.model_dump_json()))
                            log.error(f"WAS Command Endpoint unreachable: {e}")

                    else:
                        command_endpoint_result = CommandEndpointResult(speech="WAS Command Endpoint not active")
                        command_endpoint_response = CommandEndpointResponse(result=command_endpoint_result)
                        asyncio.ensure_future(websocket.send_text(command_endpoint_response.model_dump_json()))
                        log.error("WAS Command Endpoint not active")

                elif msg["cmd"] == "get_config":
                    asyncio.ensure_future(websocket.send_text(build_msg(get_config_db(), "config")))

            elif "goodbye" in msg:
                app.connmgr.disconnect(websocket)

            elif "hello" in msg:
                if "hostname" in msg["hello"]:
                    app.connmgr.update_client(websocket, "hostname", msg["hello"]["hostname"])
                if "hw_type" in msg["hello"]:
                    platform = msg["hello"]["hw_type"].upper()
                    app.connmgr.update_client(websocket, "platform", platform)
                if "mac_addr" in msg["hello"]:
                    mac_addr = hex_mac(msg["hello"]["mac_addr"])
                    app.connmgr.update_client(websocket, "mac_addr", mac_addr)

    except WebSocketDisconnect:
        app.connmgr.disconnect(websocket)
    except ConnectionClosed:
        app.connmgr.disconnect(websocket)
    except Exception as e:
        log.error(f"unhandled exception in WebSocket route: {e}")
