# Бэкап конфигурации KeeneticOS
<img src="https://github.com/user-attachments/assets/789cf6e7-848f-44dc-804c-38f84e65c5d5" alt="" width="700">

## Работа сервиса
- Выбор объектов бэкапа состоит из: `Startup-Config`, `Entware`, `Firmware` и `WireGuard Private-Keys`
- Полученный архив с копией устройства можно сохранить/отправить в Telegram/GoogleDrive и/или смонтированный раздел (внешний накопитель/WebDav).
- Расписание по умолчанию задаётся в `/opt/etc/keensnap/defaults.conf`. Если его нужно изменить, укажите `CRON_SCHEDULE` в `/opt/etc/keensnap/config.conf` и примените через Entware cron.
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
1. Откройте `/opt/etc/keensnap/config.conf`.
2. Укажите только параметры, которые нужно изменить относительно значений по умолчанию.
3. Минимально обычно нужны `SELECTED_DRIVE`, выбранные объекты бэкапа и параметры отправки.
4. Если нужно изменить расписание, задайте `CRON_SCHEDULE` в стандартном cron-синтаксисе из 5 полей, например `CRON_SCHEDULE="30 4 * * 1"`.
5. Выполните `keensnap apply`, либо переустановите пакет: cron-запись будет создана из итогового значения `CRON_SCHEDULE`.
6. Для отключения автоматического запуска добавьте `CRON_SCHEDULE=""`.

## Конфигурация `config.conf`

Пользовательский файл конфигурации находится в `/opt/etc/keensnap/config.conf` и читается как shell-файл. В него нужно добавлять только строки, которые отличаются от значений по умолчанию.

Значения по умолчанию находятся в `/opt/etc/keensnap/defaults.conf`. Этот файл поставляется пакетом и может обновляться вместе с программой, поэтому обычно его не редактируют.

Формат строки:

```shell
PARAMETER="value"
PARAMETER_BOOL=true
```

Строковые значения берите в двойные кавычки. Булевые параметры задавайте без кавычек: `true` или `false`. Если параметр не указан в `config.conf`, используется значение из `defaults.conf`. После изменения расписания выполните `keensnap apply`, чтобы обновить cron-запись.

### Служебные параметры

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `LOG_FILE` | `/opt/var/log/keensnap.log` | Путь к лог-файлу KeenSnap. Лог также попадает в созданный архив. | Обычно не менять. Если меняете, укажите полный путь к файлу, доступный для записи. |
| `LOG_MAX_SIZE_KB` | `512` | Максимальный размер лог-файла в KiB. При превышении лимита файл обрезается до последних 400 строк. | Целое число KiB. `0` отключает ротацию лога. |
| `PATH_SNAPD` | `/opt/root/KeenSnap/keensnap-init` | Путь к основному скрипту запуска бэкапа. | Обычно не менять. Нужен только при нестандартной установке. |
| `CRON_SCHEDULE` | `0 3 * * *` | Расписание автоматического запуска через Entware cron. | Строка из 5 cron-полей: `минута час день_месяца месяц день_недели`. Пример: `CRON_SCHEDULE="30 4 * * 1"` для запуска по понедельникам в 04:30. Пустое значение `CRON_SCHEDULE=""` отключает автозапуск. |

### Куда сохранять архив

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `SELECTED_DRIVE` | пусто | Локальный путь к смонтированному накопителю или внутреннему хранилищу, где временно создаётся папка бэкапа и итоговый архив. Без него бэкап не сможет создаться. | Например `/storage` или путь к USB/WebDAV-разделу вида `/tmp/mnt/<uuid>` либо `/tmp/mnt/<uuid>/<folder>`. Путь должен существовать и быть доступен для записи. |
| `DELETE_LOCAL_ARCHIVE_AFTER_BACKUP` | `false` | Удалять ли итоговый архив с `SELECTED_DRIVE` после успешной отправки. | `true`, если архив нужен только в Telegram/Google Drive/WebDAV. `false`, если нужно хранить локальную копию. Если отправка не удалась, при `true` архив также удаляется. |
| `RETAIN_ARCHIVES_DAYS` | `0` | Автоочистка старых локальных архивов на `SELECTED_DRIVE`. | Целое число дней. `0` отключает очистку. Например `14` удаляет архивы старше 14 дней. Работает только для локально сохранённых архивов. |

### Что включать в бэкап

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `BACKUP_STARTUP_CONFIG` | `false` | Сохранять `startup-config` KeeneticOS. | `true` или `false`. Обычно это основной файл конфигурации роутера. |
| `BACKUP_FIRMWARE` | `false` | Сохранять файл прошивки из `flash:/firmware`. | `true` или `false`. Учитывайте размер архива. |
| `BACKUP_ENTWARE` | `false` | Архивировать содержимое `/opt`, то есть установленную Entware-среду. | `true` или `false`. Может занимать много места. |
| `ENTWARE_EXCLUDE` | пусто | Исключения из Entware-бэкапа. | Список путей или шаблонов относительно `/opt`, разделённых пробелами. Пример: `ENTWARE_EXCLUDE="var/log tmp cache"`. |
| `BACKUP_WG_PRIVATE_KEY` | `false` | Сохранять приватные ключи WireGuard через `wg show all private-key`. | `true` или `false`. Включайте только если понимаете риск хранения приватных ключей. Рекомендуется использовать `ARCHIVE_PASSWORD`. |
| `ARCHIVE_PASSWORD` | пусто | Пароль для итогового архива. | Пустое значение создаёт `.tar.gz` без пароля. Непустое значение создаёт `.7z` с паролем, например `ARCHIVE_PASSWORD="strong-password"`. |

### Отправка архива

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `UPLOAD_METHOD` | пусто | Куда отправлять итоговый архив. | Один или несколько методов: `Telegram`, `GDrive`, `WebDAV`, `S3`. Можно разделять пробелом или запятой, например `UPLOAD_METHOD="Telegram,GDrive"` или `UPLOAD_METHOD="Telegram S3"`. Пустое значение отключает отправку, но архив может остаться локально. |
| `HASHTAG` | `#KeenSnap` | Строка, которая добавляется в конец отчёта Telegram. | Любой текст или пустая строка `HASHTAG=""`, если хэштег не нужен. |
| `PROXY_INTERFACE` | пусто | Сетевой интерфейс, через который `curl` выполняет отправку. | Имя интерфейса, например `wg0`, если отправку нужно пустить через конкретный интерфейс. Пусто - использовать маршрут системы. |
| `TG_PROXY` | пусто | Proxy для сетевых запросов `curl`. Используется не только для Telegram, а для всех отправок, которые идут через общий сетевой helper. | URL proxy в формате, поддерживаемом `curl`, например `socks5h://127.0.0.1:1080` или `http://user:pass@host:port`. |

### Telegram

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `BOT_TOKEN` | пусто | Токен Telegram-бота для отправки сообщений и файлов. | Токен от [BotFather](https://t.me/BotFather), например `123456:ABC...`. Обязателен для `UPLOAD_METHOD="Telegram"` или `TELEGRAM_SUCCESS_NOTIFY=true`. |
| `CHAT_ID` | пусто | ID пользователя, группы, канала или темы форума Telegram. | ID чата. Для темы форума поддерживается формат `chat_id_topic_id`, например `-1001234567890_42`. Обязателен для Telegram-отправки и уведомления об успехе. |
| `TELEGRAM_SUCCESS_NOTIFY` | `false` | Отправлять короткое Telegram-сообщение после успешного завершения бэкапа. | `true` или `false`. Работает независимо от `UPLOAD_METHOD` и использует `BOT_TOKEN`/`CHAT_ID`. |

### Google Drive

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `GD_CLIENT_ID` | пусто | OAuth Client ID Google Cloud. | Значение из OAuth client. Обязательно для `UPLOAD_METHOD="GDrive"`. |
| `GD_CLIENT_SECRET` | пусто | OAuth Client secret Google Cloud. | Значение из OAuth client. Обязательно для Google Drive. |
| `GD_REFRESH_TOKEN` | пусто | Refresh token для получения временного access token. | Refresh token, полученный через OAuth Playground или другой OAuth-flow. Обязателен для Google Drive. |
| `GD_FOLDER_ID` | пусто | ID папки Google Drive, куда загружать архив. | ID папки из URL Google Drive. Если оставить пустым, архив загрузится в корень доступной области приложения. |

### WebDAV

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `WD_URL` | пусто | URL назначения для загрузки архива по WebDAV. | Обязателен для `UPLOAD_METHOD="WebDAV"`. Если URL заканчивается `/`, имя архива добавится автоматически. Если URL без завершающего `/`, он считается полным путём к файлу. |
| `WD_USERNAME` | пусто | Логин WebDAV. | Логин, если сервер требует авторизацию. Можно оставить пустым для WebDAV без авторизации. |
| `WD_PASSWORD` | пусто | Пароль WebDAV. | Пароль или app-password от WebDAV-сервиса. Можно оставить пустым для WebDAV без авторизации. |
| `WD_INSECURE` | `false` | Отключить проверку TLS-сертификата при WebDAV-загрузке. | `true` только для самоподписанных сертификатов или тестовых серверов. Для обычного HTTPS оставляйте `false`. |

### S3

Для отправки в S3 используется `s3cmd`. Пакет устанавливает `python3` и `python3-pip`, затем при установке KeenSnap запускает `python3 -m pip install --no-cache-dir s3cmd`, если `s3cmd` ещё не найден.

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `S3_ENDPOINT` | пусто | Endpoint S3-совместимого хранилища. | Endpoint с протоколом или без него, например `https://s3.example.com` или `s3.example.com`. Для `http://` будет отключён HTTPS в конфиге `s3cmd`. |
| `S3_BUCKET_NAME` | пусто | Имя bucket, куда загружать архив. | Только имя bucket, без `s3://`. |
| `S3_KEY` | пусто | Access key. | Ключ доступа S3/IAM-пользователя. |
| `S3_SECRET` | пусто | Secret key. | Секретный ключ S3/IAM-пользователя. |
| `S3_PREFIX` | пусто | Папка/префикс внутри bucket. | Например `routers/home` загрузит архив в `s3://bucket/routers/home/<archive>`. Начальный и конечный `/` можно не указывать. |
| `S3_RETAIN_BACKUPS` | `0` | Ротация архивов в S3 по количеству. | `0` отключает ротацию. Например `10` хранит последние 10 архивов KeenSnap в указанном `S3_PREFIX`, более старые удаляются. |

### Обновления

| Параметр | Значение по умолчанию | Что означает | Что указывать |
| --- | --- | --- | --- |
| `AUTO_UPDATE` | `true` | После завершения бэкапа проверять новую версию и при наличии обновляться через `opkg install keensnap`. | `true` для автообновления, `false` чтобы обновлять вручную командой `keensnap update`. |

### Примеры конфигурации

`config.conf` должен содержать только отличия от дефолтов. Например, если подходит стандартное расписание `0 3 * * *`, эту строку можно не указывать.

Минимальный бэкап `startup-config` в Telegram:

```shell
SELECTED_DRIVE="/storage"
BACKUP_STARTUP_CONFIG=true
BOT_TOKEN="123456:ABC..."
CHAT_ID="123456789"
```

Локальный бэкап Entware и конфигурации без отправки:

```shell
SELECTED_DRIVE="/tmp/mnt/<uuid>/KeenSnap"
BACKUP_STARTUP_CONFIG=true
BACKUP_ENTWARE=true
ENTWARE_EXCLUDE="var/log tmp"
UPLOAD_METHOD=""
RETAIN_ARCHIVES_DAYS=30
```

Отправка в несколько мест с удалением локального архива:

```shell
SELECTED_DRIVE="/storage"
BACKUP_STARTUP_CONFIG=true
BACKUP_FIRMWARE=true
UPLOAD_METHOD="Telegram,GDrive,WebDAV"
DELETE_LOCAL_ARCHIVE_AFTER_BACKUP=true
```

Отправка в S3:

```shell
SELECTED_DRIVE="/storage"
BACKUP_STARTUP_CONFIG=true
UPLOAD_METHOD="S3"
S3_ENDPOINT="https://s3.example.com"
S3_BUCKET_NAME="keensnap-backups"
S3_KEY="access-key"
S3_SECRET="secret-key"
S3_PREFIX="routers/home"
S3_RETAIN_BACKUPS=10
```

S3-бэкап с Telegram-уведомлением об успешном завершении:

```shell
SELECTED_DRIVE="/storage"
BACKUP_STARTUP_CONFIG=true
UPLOAD_METHOD="S3"
S3_ENDPOINT="https://s3.example.com"
S3_BUCKET_NAME="keensnap-backups"
S3_KEY="access-key"
S3_SECRET="secret-key"
BOT_TOKEN="123456:ABC..."
CHAT_ID="123456789"
TELEGRAM_SUCCESS_NOTIFY=true
```

## Команды

```
keensnap help      # справка
keensnap status    # краткий статус
keensnap config    # вывести пользовательский config.conf и недостающие дефолты
keensnap logs      # вывести лог
keensnap apply     # применить конфиг и обновить cron
keensnap backup    # запустить бэкап вручную
keensnap update    # обновить пакет через opkg
```

Если текущая shell-сессия не видит `/opt/bin`, команду можно вызвать полным путём: `/opt/bin/keensnap`.

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
