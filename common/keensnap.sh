#!/bin/sh
trap cleanup HUP INT TERM

CONFIG_FILE="/opt/root/KeenSnap/config.conf"
RED='\033[1;31m'
GREEN='\033[1;32m'
CYAN='\033[0;36m'
NC='\033[0m'
USERNAME="KirillShchetinnikov"
REPO="keensnap"
SCRIPT="keensnap.sh"
KEENSNAP_DIR="/opt/root/KeenSnap"
SNAPD="keensnap-init"
CRON_FILE="/opt/etc/crontab"
CRON_MARKER="# KeenSnap"
LOG_FILE="/opt/var/log/keensnap.log"
SCRIPT_VERSION=""

print_help() {
  cat <<EOF
KeenSnap ${SCRIPT_VERSION}

Использование:
  keensnap <команда>

Команды:
  help, -h, --help      Показать эту справку
  version              Показать версию
  status               Показать краткий статус устройства и конфигурации
  config               Вывести $CONFIG_FILE
  logs                 Вывести $LOG_FILE
  apply                Применить $CONFIG_FILE и обновить cron
  backup               Запустить бэкап вручную
  update               Обновить пакет через opkg

Конфигурация:
  Все параметры задаются только в файле:
    $CONFIG_FILE

  Расписание задаётся в cron-синтаксисе из 5 полей:
    CRON_SCHEDULE="0 3 * * *"

  Чтобы отключить автоматический запуск:
    CRON_SCHEDULE=""

Примеры:
  keensnap status
  keensnap apply
  keensnap backup
  keensnap logs
EOF
}

print_message() {
  local message="$1"
  local color="${2:-$NC}"
  printf "${color}%s${NC}\n" "$message"
}

rci_request() {
  local endpoint="$1"
  curl -s "http://localhost:79/rci/$endpoint"
}

get_device() {
  rci_request "show/version" | grep -o '"device": "[^"]*"' | cut -d'"' -f4 2>/dev/null
}

get_fw_version() {
  rci_request "show/version" | grep -o '"release": "[^"]*"' | cut -d'"' -f4 2>/dev/null
}

get_hw_id() {
  rci_request "show/version" | grep -o '"hw_id": "[^"]*"' | cut -d'"' -f4 2>/dev/null
}

get_config_raw() {
  local key="$1"
  grep "^$key=" "$CONFIG_FILE" 2>/dev/null | head -n 1 | cut -d '=' -f2-
}

get_config_value() {
  local key="$1"
  get_config_raw "$key" | sed 's/^"//;s/"$//'
}

get_config_bool() {
  local key="$1"
  local default="$2"
  local value
  value=$(get_config_raw "$key")
  case "$value" in
  true | false) echo "$value" ;;
  *) echo "$default" ;;
  esac
}

get_backup_content() {
  local selected=""
  local entry
  local key
  local label

  for entry in \
    "BACKUP_STARTUP_CONFIG:Startup-Config" \
    "BACKUP_FIRMWARE:Firmware" \
    "BACKUP_ENTWARE:Entware" \
    "BACKUP_WG_PRIVATE_KEY:WireGuard-Private-Key"; do
    key=${entry%%:*}
    label=${entry#*:}
    [ "$(get_config_bool "$key" "false")" = "true" ] && selected="${selected}${selected:+, }$label"
  done

  [ -n "$selected" ] && echo "$selected"
}

setup_config() {
  mkdir -p "$KEENSNAP_DIR"
  if [ ! -f "$CONFIG_FILE" ]; then
    print_message "Файл конфигурации не найден. Переустановите пакет $REPO" "$RED"
    return 1
  fi

  if command -v dos2unix >/dev/null 2>&1; then
    dos2unix "$CONFIG_FILE" >/dev/null 2>&1
  else
    sed -i 's/\r$//' "$CONFIG_FILE"
  fi
}

check_config() {
  setup_config || exit 1
}

show_status() {
  check_config

  local device
  local hw_id
  local fw_version
  local cron_schedule
  local selected_drive
  local upload_methods
  local backup_content

  device=$(get_device)
  hw_id=$(get_hw_id)
  fw_version=$(get_fw_version)
  cron_schedule=$(get_config_value "CRON_SCHEDULE")
  selected_drive=$(get_config_value "SELECTED_DRIVE")
  upload_methods=$(get_config_value "UPLOAD_METHOD")
  backup_content=$(get_backup_content)

  [ -z "$device" ] && device="unknown"
  [ -z "$hw_id" ] && hw_id="unknown"
  [ -z "$fw_version" ] && fw_version="unknown"
  [ -z "$cron_schedule" ] && cron_schedule="disabled"
  [ -z "$selected_drive" ] && selected_drive="not set"
  [ -z "$upload_methods" ] && upload_methods="not set"
  [ -z "$backup_content" ] && backup_content="not set"

  printf "${CYAN}Модель:${NC} %s (%s)\n" "$device" "$hw_id"
  printf "${CYAN}KeeneticOS:${NC} %s\n" "$fw_version"
  printf "${CYAN}Версия KeenSnap:${NC} %s by %s\n" "$SCRIPT_VERSION" "$USERNAME"
  printf "${CYAN}Cron:${NC} %s\n" "$cron_schedule"
  printf "${CYAN}Накопитель:${NC} %s\n" "$selected_drive"
  printf "${CYAN}Отправка:${NC} %s\n" "$upload_methods"
  printf "${CYAN}Состав:${NC} %s\n" "$backup_content"
}

show_config() {
  check_config
  cat "$CONFIG_FILE"
}

show_logs() {
  check_config
  if [ -f "$LOG_FILE" ]; then
    cat "$LOG_FILE"
  else
    echo "Лог-файл пока не создан"
  fi
}

validate_cron_schedule() {
  local cron_schedule="$1"
  set -f
  set -- $cron_schedule
  set +f
  [ "$#" -eq 5 ]
}

restart_cron() {
  if [ -x "/opt/etc/init.d/S10cron" ]; then
    /opt/etc/init.d/S10cron restart >/dev/null 2>&1 && return 0
    /opt/etc/init.d/S10cron start >/dev/null 2>&1 && return 0
  fi

  if command -v crond >/dev/null 2>&1; then
    killall crond >/dev/null 2>&1
    crond >/dev/null 2>&1 && return 0
  fi

  return 1
}

apply_cron_schedule() {
  check_config

  local cron_schedule
  cron_schedule=$(get_config_value "CRON_SCHEDULE")

  if [ -n "$cron_schedule" ] && ! validate_cron_schedule "$cron_schedule"; then
    print_message "CRON_SCHEDULE должен содержать 5 cron-полей" "$RED"
    return 1
  fi

  mkdir -p "$(dirname "$CRON_FILE")"
  touch "$CRON_FILE"
  sed -i "\|$CRON_MARKER|d" "$CRON_FILE"

  if [ -n "$cron_schedule" ]; then
    printf '%s %s start cron %s\n' "$cron_schedule" "$KEENSNAP_DIR/$SNAPD" "$CRON_MARKER" >>"$CRON_FILE"
  fi

  if restart_cron; then
    print_message "Конфиг применён" "$GREEN"
  else
    print_message "Cron-запись обновлена, но cron не перезапущен" "$RED"
    return 1
  fi
}

manual_backup() {
  check_config
  "$KEENSNAP_DIR/$SNAPD" start manual
}

packages_checker() {
  local missing=""
  for pkg in "$@"; do
    if ! opkg list-installed | grep -q "^$pkg"; then
      missing="$missing $pkg"
    fi
  done
  if [ -n "$missing" ]; then
    opkg update && opkg install $missing
    echo ""
  fi
}

script_update() {
  local mode="${1:-manual}"
  packages_checker curl tar ca-certificates wget-ssl jq cron
  if opkg update && opkg install "$REPO"; then
    if [ "$mode" = "silent" ]; then
      logger -p notice -t KeenSnap "Пакет обновлён в silent-режиме"
    else
      print_message "Пакет обновлён" "$GREEN"
    fi
    exit 0
  fi

  if [ "$mode" = "silent" ]; then
    logger -p err -t KeenSnap "Ошибка при обновлении пакета"
  else
    print_message "Не удалось обновить пакет. Выполните обновление вручную." "$RED"
  fi
  exit 1
}

cleanup() {
  pkill -P $$ 2>/dev/null
}

case "${1:-help}" in
  help|-h|--help)
    print_help
    ;;
  version|--version)
    echo "$SCRIPT_VERSION"
    ;;
  status)
    show_status
    ;;
  config|show-config)
    show_config
    ;;
  logs|show-logs)
    show_logs
    ;;
  apply|apply-config)
    apply_cron_schedule
    ;;
  backup|run|start)
    manual_backup
    ;;
  update)
    script_update "manual"
    ;;
  script_update)
    script_update "$2"
    ;;
  *)
    print_message "Неизвестная команда: $1" "$RED" >&2
    echo "" >&2
    print_help >&2
    exit 1
    ;;
esac
