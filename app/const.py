from semver import Version


ALEMBIC_CONFIG = '/app/alembic.ini'
DB_URL = 'sqlite:////app/storage/was.db'
DIR_ASSET = '/app/storage/asset'
DIR_OTA = '/app/storage/ota'
URL_WILLOW_RELEASES = 'https://worker.heywillow.org/api/release?format=was'
URL_WILLOW_CONFIG = 'https://worker.heywillow.org/api/config'
URL_WILLOW_TZ = 'https://worker.heywillow.org/api/asset?type=tz'

# Willow 0.5 beta introduces SR model OTA, which WAS 0.3 cannot provide.
WILLOW_MIN_SR_MODEL_OTA_VERSION = Version.parse("0.5.0-beta.0")

STORAGE_USER_CLIENT_CONFIG = 'storage/user_client_config.json'
STORAGE_USER_CONFIG = 'storage/user_config.json'
STORAGE_USER_MULTINET = 'storage/user_multinet.json'
STORAGE_USER_NVS = 'storage/user_nvs.json'
STORAGE_USER_WAS = 'storage/user_was.json'
STORAGE_TZ = 'storage/tz.json'
