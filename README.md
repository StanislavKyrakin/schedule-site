# Сайт расписания: Google Sheets → Cloud Run

Этот проект — готовая замена версии с Excel. HTML/CSS сохраняются, но источник данных теперь Google Sheets.

## 1. Структура Google Sheets

В одной Google Таблице должны быть листы:

- `Классы`
- `Дни`
- `Предметы` (необязательно для текущего отображения)
- `Расписание`
- `Соцсети`
- `Полезные ссылки`
- `Настройки`

Заголовки листов совпадают с вашим исходным Excel-шаблоном.

### Классы

`Class ID | Класс | Классный руководитель | Кабинет | Активен`

### Расписание

`Class ID | Day ID | № урока | Время начала | Время окончания | Предмет | Кабинет | Учитель | Примечание | Активен`

### Соцсети

`Class ID | Тип | Название | URL | Показывать`

### Полезные ссылки

`Class ID | Категория | Название | Описание | URL | Порядок | Показывать`

### Настройки

`Параметр | Значение | Описание`

Например: `Основной класс | 1`, `Год в футере | 2026`.

## 2. Google Cloud

Создайте Google Cloud Project и включите:

- Cloud Run API
- Cloud Build API
- Artifact Registry API
- Google Sheets API

Создайте service account:

`schedule-site@PROJECT_ID.iam.gserviceaccount.com`

Этому service account нужно дать доступ Viewer к самой Google Таблице через кнопку «Поделиться».

## 3. Найдите Spreadsheet ID

Из URL:

`https://docs.google.com/spreadsheets/d/XXXXXXXX/edit`

нужна только часть:

`XXXXXXXX`

## 4. Деплой

### Windows PowerShell

```powershell
gcloud auth login
gcloud config set project PROJECT_ID
.\deploy.ps1 -ProjectId PROJECT_ID -SpreadsheetId SPREADSHEET_ID
```

### Linux/macOS

```bash
gcloud auth login
./deploy.sh PROJECT_ID SPREADSHEET_ID
```

Можно выполнить непосредственно:

```bash
gcloud run deploy schedule-site   --source .   --region europe-west1   --service-account schedule-site@PROJECT_ID.iam.gserviceaccount.com   --allow-unauthenticated   --set-env-vars SPREADSHEET_ID=SPREADSHEET_ID,SHEETS_CACHE_SECONDS=30
```

Cloud Run умеет разворачивать проект напрямую из исходников через `gcloud run deploy --source .`; при наличии Dockerfile будет использован Dockerfile.

## 5. Проверка

После деплоя Cloud Run покажет URL, например:

`https://schedule-site-xxxxx-ew.a.run.app`

Проверка соединения с Google Sheets:

`https://ВАШ_URL/health`

Административная страница:

`https://ВАШ_URL/admin`

Обновить данные вручную:

`https://ВАШ_URL/refresh`

## 6. Как обновлять расписание

Открываете Google Sheets → меняете данные → сохраняете → сайт увидит новые данные при следующем чтении.

По умолчанию приложение держит данные в памяти 30 секунд (`SHEETS_CACHE_SECONDS`), чтобы не делать запрос в Google Sheets на каждый клик. При необходимости можно поставить `0`, чтобы отключить кэш.

## 7. Безопасность

Не помещайте JSON-ключ service account в репозиторий.

На Cloud Run приложение использует Application Default Credentials, то есть права назначенного Cloud Run service account.

Для публичного сайта `--allow-unauthenticated` относится к доступу к самому сайту. Доступ к Google Sheets по-прежнему контролируется отдельно через права service account.

## 8. Ссылки на страницы

- `/` — основной класс
- `/class/1` — класс 5-А при Class ID = 1
- `/class/1/day/1` — понедельник
- `/admin` — состояние источника данных
- `/health` — техническая проверка
- `/refresh` — принудительное обновление

