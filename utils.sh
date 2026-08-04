#!/bin/sh
set -e
WAS_DIR=$(CDPATH= cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)
cd "$WAS_DIR"

# Test for local environment file and use any overrides
if [ -r .env ]; then
    echo "Using configuration overrides from .env file"
    . ./.env
else
    echo "Using default configuration values"
    touch .env
fi

# Import the .env file
set -a
. ./.env

# Which docker image to run
IMAGE=${IMAGE:-willow-application-server}

# UI Listen port
UI_LISTEN_PORT=${UI_LISTEN_PORT:-8501}

# API Listen Port
API_LISTEN_PORT=${API_LISTEN_PORT:-8502}

# Log level - acceptable values are debug, info, warning, error, critical. Suggest info or debug.
LOG_LEVEL=${LOG_LEVEL:-info}

# Listen IP
LISTEN_IP=${LISTEN_IP:-0.0.0.0}

TAG=${TAG:-latest}

# Torture delay
TORTURE_DELAY=${TORTURE_DELAY:-300}

# Web ui branch
WEB_UI_BRANCH="main"

# Local working directory for web ui
WEB_UI_DIR="willow-application-server-ui"

# Web ui URL
WEB_UI_URL="https://github.com/HeyWillow/willow-application-server-ui.git"

# Reachable WAS IP for the "default" interface
case "$(uname -s)" in
    Darwin)
        WAS_INTERFACE=$(route get default 2>/dev/null | awk '/interface:/ { print $2; exit }')
        if [ -n "$WAS_INTERFACE" ]; then
            WAS_IP=$(ifconfig "$WAS_INTERFACE" | awk '$1 == "inet" { print $2; exit }')
        else
            WAS_IP=""
        fi
        ;;
    Linux)
        WAS_ROUTE=$(ip route get 1.1.1.1)
        case "$WAS_ROUTE" in
            *" src "*)
                WAS_IP=${WAS_ROUTE#* src }
                WAS_IP=${WAS_IP%% *}
                ;;
            *)
                WAS_IP=""
                ;;
        esac
        ;;
    *)
        WAS_IP=""
        ;;
esac

# Get WAS version
export WAS_VERSION=$(git describe --always --dirty --tags)

set +a

if [ -z "$WAS_IP" ]; then
    echo "Could not determine WAS IP address - you will need to add it to .env"
    exit 1
else
    echo "WAS Web UI URL is http://$WAS_IP:$API_LISTEN_PORT"
fi

set +a

dep_check() {
    return
}

build_docker() {
    docker build --build-arg "WAS_VERSION=$WAS_VERSION" -t "$IMAGE":"$TAG" .
}

build_web_ui() {
    mkdir -p "$WAS_DIR"/work
    cd "$WAS_DIR"/work
    if [ -d "$WEB_UI_DIR/node_modules" ]; then
        echo "Existing web ui working dir found, we need sudo to remove it because of docker"
        sudo rm -rf willow-application-server-ui
    fi
    git clone "$WEB_UI_URL"
    cd willow-application-server-ui
    git checkout "$WEB_UI_BRANCH"
    ./utils.sh build-docker
    ./utils.sh install
    # WAS_DIR is already set
    export WAS_DIR
    ./utils.sh build
}

shell() {
    docker run -it -v "$WAS_DIR:/app" -v "$WAS_DIR/cache:/root/.cache" -v willow-application-server_was-storage:/app/storage "$IMAGE":"$TAG" \
        /bin/sh
}

case $1 in

build-docker|build)
    build_docker
;;

build-web-ui)
    build_web_ui
;;

start|run|up)
    dep_check
    shift
    docker compose up --remove-orphans "$@"
;;

stop|down)
    dep_check
    shift
    docker compose down "$@"
;;

shell|docker)
    shell
;;

test)
    dep_check
    docker run --rm -it --env PYTHONPATH=/app --volume="${WAS_DIR}:/app" "$IMAGE":"$TAG" pytest
;;

torture)
    echo "Starting WAS device torture test"
    docker compose down
    while true; do
        docker compose up -d
        echo "Sleeping for $TORTURE_DELAY"
        sleep $TORTURE_DELAY
        docker compose down
        "Sleeping for $TORTURE_DELAY"
        sleep $TORTURE_DELAY
    done
;;

*)
    dep_check
    echo "Passing unknown argument directly to docker compose"
    docker compose "$@"
;;

esac
