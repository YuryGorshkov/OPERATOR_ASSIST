# Установка из Git-репозитория

**Русский** | [English](install-from-git.en.md)

Это руководство предназначено для установки `OPERATOR_ASSIST` напрямую из исходного кода публичного репозитория GitHub вместо готового выпуска.

## Что потребуется

Перед началом подготовьте:

- Windows 10 или Windows 11;
- установленный Git;
- Python `3.10.x` или новее;
- одну из поддерживаемых русских моделей Vosk.

## Клонирование репозитория

Откройте PowerShell или Windows Terminal и выполните:

```powershell
git clone https://github.com/YuryGorshkov/OPERATOR_ASSIST.git
cd OPERATOR_ASSIST
```

## Настройка исходного кода

В репозитории есть установочный скрипт, который создаёт локальное виртуальное окружение, устанавливает зависимости, подготавливает рабочие каталоги и проверяет среду:

```text
Setup-From-Git.cmd
```

Эквивалентная команда PowerShell:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup-From-Git.ps1
```

По умолчанию скрипт:

1. находит подходящий интерпретатор Python;
2. создаёт `.venv` внутри репозитория;
3. устанавливает зависимости из `requirements.txt`;
4. создаёт каталоги `models/`, `logs/` и `transcripts/`;
5. запускает `scripts/Check-Environment.ps1`.

Стандартный набор зависимостей включает точный режим на основе `faster-whisper`. Поэтому после чистой установки режим Whisper уже доступен в интерфейсе, но при первом использовании выбранная модель может дополнительно загрузиться в `models/whisper-cache`.

## Добавление модели Vosk

Поместите поддерживаемую русскую модель Vosk в один из каталогов:

- `models/vosk-model-ru-0.42`
- `models/vosk-model-ru-0.22`
- `models/vosk-model-small-ru-0.22`

Модель должна быть распакована в обычный каталог, а не оставлена в ZIP-архиве.

## Запуск приложения

После завершения установки запустите:

```text
Run-Operator-Assist.cmd
```

Если внутри проекта существует `.venv`, командный файл автоматически использует это окружение. Такая установка остаётся изолированной от остальных проектов Python.

При выборе точного режима первый запуск модели займёт заметно больше времени, чем запуск Vosk.

## Повторная проверка среды

Выполните:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Check-Environment.ps1
```

## Дополнительные параметры

Скрипт установки поддерживает дополнительные параметры:

- `-NoVenv` — использовать текущее окружение Python вместо создания `.venv`;
- `-SkipPackageInstall` — не устанавливать уже подготовленные зависимости;
- `-SkipEnvironmentCheck` — выполнить только первоначальную настройку без проверки среды.

Пример:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup-From-Git.ps1 -SkipEnvironmentCheck
```
