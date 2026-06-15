# Бэкап конфигурации KeeneticOS
<img src="https://github.com/user-attachments/assets/789cf6e7-848f-44dc-804c-38f84e65c5d5" alt="" width="700">

## Работа сервиса
- Выбор объектов бэкапа состоит из: `Startup-Config`, `Entware`, `Firmware` и `WireGuard Private-Keys`
- Полученный архив с копией устройства можно сохранить/отправить в Telegram/GoogleDrive и/или смонтированный раздел (внешний накопитель/WebDav).
- Расписание задаётся в `/opt/root/KeenSnap/config.conf` в параметре `CRON_SCHEDULE` и применяется через Entware cron.
- Просмотр логов: `cat /opt/var/log/keensnap.log` или журнале KeeneticOS. Они сохраняются в каждом созданном архиве.

# Автоустановка

```shell
opkg update && opkg install curl ca-certificates wget-ssl && curl -fsSL https://gh.kipik1.ru/install.sh | sh
```

### Ручная установка

1. Установите необходимые зависимости
   ```
   opkg update && opkg install ca-certificates wget-ssl && opkg remove wget-nossl
   ```
2. Установите opkg-репозиторий в систему
   ```
   curl -fsSL https://gh.kipik1.ru/add-repo.sh | sh
   ```

3. Установите пакет
   ```
   opkg update && opkg install keensnap
   ```  

# Настройка
1. Откройте `/opt/root/KeenSnap/config.conf`.
2. Заполните параметры бэкапа, отправки и накопителя в этом файле.
3. Задайте расписание в `CRON_SCHEDULE` в стандартном cron-синтаксисе из 5 полей, например `CRON_SCHEDULE="0 3 * * *"`.
4. Выполните `keensnap apply`, либо переустановите пакет: cron-запись будет создана из `CRON_SCHEDULE`.
5. Для отключения автоматического запуска оставьте `CRON_SCHEDULE=""`.

## Команды

```
keensnap help      # справка
keensnap status    # краткий статус
keensnap config    # вывести конфиг
keensnap logs      # вывести лог
keensnap apply     # применить конфиг и обновить cron
keensnap backup    # запустить бэкап вручную
keensnap update    # обновить пакет через opkg
```

## Сборка IPK и opkg-репозитория

```
make keensnap-ipk
make feed
```

`make keensnap-ipk` создаёт пакет `out/keensnap_<version>_all.ipk`.
`make feed` создаёт структуру `out/feed/<arch>/Packages.gz` для публикации через GitHub Pages или другой HTTP-сервер.

По умолчанию `add-repo.sh` использует `https://gh.kipik1.ru`.
Для другого адреса можно передать `FEED_URL`:

```
FEED_URL="https://example.com/keensnap" sh add-repo.sh
```

В репозитории есть workflow `.github/workflows/publish-feed.yml`: он запускает `make feed` и публикует `out/feed` в ветку `gh-pages`. В настройках GitHub Pages нужно один раз выбрать источник `Deploy from a branch`, ветку `gh-pages`, директорию `/`.

<details>
  <summary>Подключение Telegram</summary>

1. Получить и скопировать `ID` своего аккаунта или чата через [UserInfoBot](https://t.me/userinfobot)
2. Создать своего бота через [BotFather](https://t.me/BotFather), скопировать его `token` и вставить в сервис

<img src="https://github.com/user-attachments/assets/ca5c31af-b29c-4d5a-b2d9-75ff64ba2c34" alt="" width="700">

</details>
<details>
  <summary>Подключение Google Drive</summary>

1. [Создать проект](https://console.cloud.google.com/projectcreate)
2. [Включить приложение Google Drive](https://console.cloud.google.com/apis/library/drive.googleapis.com)
3. [Создать приложение](https://console.cloud.google.com/auth/overview/create )
4. В [credentials](https://console.cloud.google.com/apis/credentials) создать `API Keys` с `Google Drive API` restrictions
5. Создать `OAuth client ID`. `Application type` -> `Web application`, `Authorized redirect URIs` -> `https://developers.google.com/oauthplayground`. Полученные Client ID и Client secret сохраняем
6. В [Playground](https://developers.google.com/oauthplayground) вписываем данные и URL `https://www.googleapis.com/auth/drive.file`. Выбираем `Authorize APIs`
<img width="1018" height="1274" alt="Screenshot_2" src="https://github.com/user-attachments/assets/dee36c9c-4338-414c-bcbc-4457d2dab643" />

7. Нажимаем `Exchange authorization code for tokens`.
8. Полученный `Refresh token`, `Client ID` и `Client secret` вставляем в сервис
<img width="490" height="643" alt="Screenshot_3" src="https://github.com/user-attachments/assets/aa705253-ecf6-49ef-be78-1b07e643aecf" />
</details>

##  Удаление

#### Пакета
```
opkg remove keensnap
```
#### Репозитория
```
rm /opt/etc/opkg/keensnap.conf
```
