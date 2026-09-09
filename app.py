from pathlib import Path
from datetime import datetime
import os
import re
import time

from flask import Flask, render_template, redirect, url_for, flash, request
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "").strip()
CACHE_SECONDS = int(os.environ.get("SHEETS_CACHE_SECONDS", "30"))

REQUIRED_SHEETS = ["Классы", "Дни", "Расписание"]
OPTIONAL_SHEETS = ["Предметы", "Соцсети", "Полезные ссылки", "Настройки"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

_cache = {"timestamp": 0.0, "data": None}


def sheets_service():
    credentials, _ = default(scopes=SCOPES)
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def read_range(service, sheet_name):
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{sheet_name}'!A:Z",
        majorDimension="ROWS",
    ).execute()
    values = result.get("values", [])
    if not values:
        return []

    headers = [str(v).strip() if v is not None else "" for v in values[0]]
    result_rows = []
    for row in values[1:]:
        if not any(str(v).strip() for v in row if v is not None):
            continue
        item = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            item[header] = row[i] if i < len(row) else ""
        result_rows.append(item)
    return result_rows


def text(value):
    if value is None:
        return ""
    return str(value).strip()


def to_int(value, default=0):
    try:
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def enabled(value):
    return text(value).lower() not in {"нет", "no", "false", "0", "off"}


def get_data(force=False):
    now = time.time()
    if not force and _cache["data"] is not None and now - _cache["timestamp"] < CACHE_SECONDS:
        return _cache["data"]

    if not SPREADSHEET_ID:
        raise RuntimeError("Не задана переменная окружения SPREADSHEET_ID.")

    service = sheets_service()

    try:
        available = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
            fields="sheets.properties.title"
        ).execute()
    except HttpError as exc:
        raise RuntimeError(
            "Не удалось открыть Google Таблицу. Проверьте SPREADSHEET_ID "
            "и доступ Cloud Run service account к таблице."
        ) from exc

    existing = {x["properties"]["title"] for x in available.get("sheets", [])}
    missing = [s for s in REQUIRED_SHEETS if s not in existing]
    if missing:
        raise RuntimeError("В Google Таблице отсутствуют листы: " + ", ".join(missing))

    sheets = {}
    for sheet_name in REQUIRED_SHEETS + OPTIONAL_SHEETS:
        if sheet_name in existing:
            sheets[sheet_name] = read_range(service, sheet_name)

    classes = [{
        "id": text(r.get("Class ID")),
        "name": text(r.get("Класс")),
        "teacher": text(r.get("Классный руководитель")),
        "room": text(r.get("Кабинет")),
        "active": enabled(r.get("Активен")),
    } for r in sheets.get("Классы", [])]

    days = [{
        "id": text(r.get("Day ID")),
        "name": text(r.get("День недели")),
        "short": text(r.get("Короткое название")),
        "order": to_int(r.get("Порядок"), 999),
    } for r in sheets.get("Дни", [])]
    days.sort(key=lambda x: x["order"])

    schedule = []
    for r in sheets.get("Расписание", []):
        if not enabled(r.get("Активен")):
            continue
        schedule.append({
            "class_id": text(r.get("Class ID")),
            "day_id": text(r.get("Day ID")),
            "lesson": to_int(r.get("№ урока")),
            "start": text(r.get("Время начала")),
            "end": text(r.get("Время окончания")),
            "subject": text(r.get("Предмет")),
            "room": text(r.get("Кабинет")),
            "teacher": text(r.get("Учитель")),
            "note": text(r.get("Примечание")),
        })

    socials = [{
        "class_id": text(r.get("Class ID")),
        "type": text(r.get("Тип")),
        "name": text(r.get("Название")),
        "url": text(r.get("URL")),
    } for r in sheets.get("Соцсети", []) if enabled(r.get("Показывать"))]

    useful = [{
        "class_id": text(r.get("Class ID")),
        "name": text(r.get("Название")),
        "description": text(r.get("Описание")),
        "url": text(r.get("URL")),
        "order": to_int(r.get("Порядок"), 999),
    } for r in sheets.get("Полезные ссылки", []) if enabled(r.get("Показывать"))]
    useful.sort(key=lambda x: x["order"])

    settings = {
        text(r.get("Параметр")): text(r.get("Значение"))
        for r in sheets.get("Настройки", [])
        if text(r.get("Параметр"))
    }

    data = {
        "classes": classes,
        "days": days,
        "schedule": schedule,
        "socials": socials,
        "useful": useful,
        "settings": settings,
        "spreadsheet_id": SPREADSHEET_ID,
        "loaded_at": datetime.now().isoformat(timespec="seconds"),
    }

    _cache["timestamp"] = now
    _cache["data"] = data
    return data


def get_class_context(class_id):
    data = get_data()
    class_obj = next(
        (c for c in data["classes"] if c["id"] == str(class_id) and c["active"]),
        None
    )
    if not class_obj:
        return None, data

    return {
        "class_obj": class_obj,
        "schedule": [x for x in data["schedule"] if x["class_id"] == class_obj["id"]],
        "socials": [x for x in data["socials"] if x["class_id"] == class_obj["id"]],
        "useful": [x for x in data["useful"] if x["class_id"] == class_obj["id"]],
    }, data


@app.context_processor
def globals_for_templates():
    try:
        data = get_data()
        settings = data["settings"]
    except Exception:
        settings = {}
    return {
        "site_title": settings.get("Название сайта", "Школьное расписание"),
        "year": settings.get("Год в футере", str(datetime.now().year)),
    }


@app.route("/")
def index():
    data = get_data()
    classes = [c for c in data["classes"] if c["active"]]
    default_id = data["settings"].get("Основной класс", "").strip()
    default = next((c for c in classes if c["id"] == default_id), classes[0] if classes else None)
    if default:
        return redirect(url_for("class_page", class_id=default["id"]))
    return render_template("index.html", classes=classes)


@app.route("/class/<class_id>")
def class_page(class_id):
    ctx, data = get_class_context(class_id)
    if not ctx:
        return render_template("404.html", message="Класс не найден"), 404

    day_cards = []
    for day in data["days"]:
        lessons = sorted(
            [x for x in ctx["schedule"] if x["day_id"] == day["id"]],
            key=lambda x: x["lesson"]
        )
        if lessons:
            day_cards.append({
                **day,
                "lessons": lessons,
                "count": len(lessons),
                "first": lessons[0]["start"],
                "last": lessons[-1]["end"],
            })

    today = next(
        (d for d in day_cards if d["order"] == datetime.now().isoweekday()),
        None
    )
    return render_template(
        "class.html",
        class_obj=ctx["class_obj"],
        day_cards=day_cards,
        today=today,
        socials=ctx["socials"],
        useful=ctx["useful"],
    )


@app.route("/class/<class_id>/day/<day_id>")
def day_page(class_id, day_id):
    ctx, data = get_class_context(class_id)
    if not ctx:
        return render_template("404.html", message="Класс не найден"), 404

    day = next((d for d in data["days"] if d["id"] == str(day_id)), None)
    if not day:
        return render_template("404.html", message="День не найден"), 404

    lessons = sorted(
        [x for x in ctx["schedule"] if x["day_id"] == str(day_id)],
        key=lambda x: x["lesson"]
    )
    return render_template("day.html", class_obj=ctx["class_obj"], day=day, lessons=lessons)


@app.route("/refresh")
def refresh():
    get_data(force=True)
    ref = request.referrer
    return redirect(ref if ref and ref.startswith(request.host_url) else url_for("index"))


@app.route("/admin", methods=["GET"])
def admin():
    data = get_data()
    return render_template(
        "admin.html",
        spreadsheet_id=data["spreadsheet_id"],
        loaded_at=data["loaded_at"],
        classes=len(data["classes"]),
        lessons=len(data["schedule"]),
        cache_seconds=CACHE_SECONDS,
    )


@app.route("/health")
def health():
    try:
        data = get_data()
        return {
            "status": "ok",
            "spreadsheet_connected": True,
            "classes": len(data["classes"]),
            "lessons": len(data["schedule"]),
            "loaded_at": data["loaded_at"],
        }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}, 500


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html", message="Страница не найдена"), 404


@app.errorhandler(Exception)
def server_error(exc):
    # Keep the user-facing message useful without exposing a traceback.
    return render_template("404.html", message=f"Ошибка загрузки данных: {exc}"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
