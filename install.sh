#!/bin/sh

printf "\033c"
set -e

printf "\nУстанавливаю репозиторий\n\n"
curl -fsSL https://gh.kipik1.ru/add-repo.sh | sh
printf "\n\nНачинаю установку\n\n"
opkg update && opkg install keensnap
