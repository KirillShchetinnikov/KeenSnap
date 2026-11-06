#!/bin/sh

DEFAULT_CONFIG_FILE="$CONFIG_DIR/config.conf"
CONFIG_OVERRIDE_DIR="$CONFIG_DIR/config.d"

load_config() {
  local config_file
  local LC_ALL=C

  if [ ! -f "$DEFAULT_CONFIG_FILE" ]; then
    echo "Файл стандартных значений не найден: $DEFAULT_CONFIG_FILE" >&2
    return 1
  fi

  . "$DEFAULT_CONFIG_FILE" || return 1
  for config_file in "$CONFIG_OVERRIDE_DIR"/*.conf; do
    [ -f "$config_file" ] || continue
    . "$config_file" || return 1
  done
  return 0
}

get_config_value() {
  local key="$1"
  case "$key" in
    ''|[0-9]*|*[!A-Za-z0-9_]*) return 1 ;;
  esac
  eval 'printf "%s\n" "${'"$key"'-}"'
}
