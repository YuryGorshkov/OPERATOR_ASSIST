"""Pure startup-readiness helpers for OPERATOR_ASSIST."""

from operator_assist_runtime.text_utils import short_text


def format_duration_short(total_seconds):
    total_seconds = max(0, int(round(float(total_seconds or 0))))
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def estimate_model_load_window_seconds(model_name):
    normalized = (model_name or "").strip().lower()
    if "small" in normalized:
        return (5, 30)
    if "0.42" in normalized:
        return (20, 180)
    if "0.22" in normalized:
        return (15, 120)
    return (15, 90)


def build_model_loading_status(
    *,
    phase,
    model_name,
    elapsed_seconds,
    attempt_index=0,
    attempt_total=0,
):
    target_name = model_name or "модель"
    elapsed_text = format_duration_short(elapsed_seconds)
    low_seconds, high_seconds = estimate_model_load_window_seconds(target_name)
    attempt_text = ""
    if attempt_total and attempt_total > 1 and attempt_index:
        attempt_text = f"Попытка {attempt_index}/{attempt_total}. "

    if elapsed_seconds > high_seconds:
        expectation = f"Это уже дольше обычного ({high_seconds}+ с), но загрузка еще может завершиться."
    else:
        expectation = f"Обычно это занимает {low_seconds}-{high_seconds} с."

    return (
        f"{attempt_text}{phase}: {short_text(target_name, limit=64)}. "
        f"Прошло {elapsed_text}. {expectation}"
    )


def build_startup_summary(
    *,
    model_loading,
    active_model_name,
    existing_model_names,
    model_error_text,
    mic_selected,
    speaker_selected,
    settings_exists,
    workers_active=False,
    settings_file_name="operator_assist_settings.json",
    mic_required=True,
    speaker_required=True,
):
    existing_model_names = [name.strip() for name in existing_model_names if name and name.strip()]
    model_ready = bool(active_model_name)
    mic_ready = not mic_required or bool((mic_selected or "").strip())
    speaker_ready = not speaker_required or bool((speaker_selected or "").strip())
    waiting_model = bool(model_loading and not model_ready)

    if model_ready:
        model_line = f"OK: модель {active_model_name} загружена."
    elif waiting_model and existing_model_names:
        model_line = f"Ждите: модель загружается ({', '.join(existing_model_names[:2])})."
    elif model_error_text:
        model_line = f"Ошибка: модель не открылась ({short_text(model_error_text, limit=110)})."
    else:
        model_line = "Нужно: добавьте одну из поддерживаемых русских моделей Vosk в папку с моделями."

    if not mic_required:
        mic_line = "OK: канал оператора выключен выбранным режимом."
    elif mic_ready:
        mic_line = f"OK: микрофон выбран ({short_text(mic_selected, limit=72)})."
    else:
        mic_line = "Нужно: выберите микрофон оператора."

    if not speaker_required:
        speaker_line = "OK: канал собеседника выключен выбранным режимом."
    elif speaker_ready:
        speaker_line = f"OK: источник собеседника выбран ({short_text(speaker_selected, limit=72)})."
    else:
        speaker_line = "Нужно: выберите источник собеседника или системного звука."

    if settings_exists:
        settings_line = f"OK: настройки сохраняются в {settings_file_name}."
    else:
        settings_line = f"Совет: файл {settings_file_name} появится после первого сохранения настроек."

    if workers_active:
        title = "Сеанс уже запущен"
        hint = "Стартовые проверки пройдены. Следите за уровнями сигнала и диагностикой аудио."
    elif model_error_text:
        title = "Ошибка загрузки модели"
        hint = "Проверьте содержимое папки с моделями, затем нажмите Проверить снова. Подробности есть в логах."
    elif not existing_model_names and not model_ready:
        title = "Нужна модель распознавания"
        hint = "Откройте папку с моделями и распакуйте туда русскую модель Vosk. После этого нажмите Проверить снова."
    elif waiting_model:
        title = "Загружаю модель"
        hint = "Большая модель может открываться заметно дольше. Кнопка Старт включится автоматически."
    elif not mic_ready or not speaker_ready:
        title = "Проверьте источники звука"
        hint = "Выберите источники, необходимые для текущего режима записи."
    elif model_ready:
        title = "Готово к запуску"
        hint = "Можно нажимать Старт. Если дорожки будут пересекаться, посмотрите блок диагностики аудио."
    else:
        title = "Подготовка первого запуска"
        hint = "Проверяю модель, устройства и сохраненные настройки."

    return {
        "title": title,
        "hint": hint,
        "model_line": model_line,
        "mic_line": mic_line,
        "speaker_line": speaker_line,
        "settings_line": settings_line,
        "ready": model_ready and mic_ready and speaker_ready and not model_loading and not workers_active,
    }
