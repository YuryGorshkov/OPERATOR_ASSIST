"""Shared technical-term normalization services for OPERATOR_ASSIST."""

import json
import re


MAX_CUSTOM_TERM_RULES = 500
MAX_CUSTOM_TERM_LENGTH = 160


def serialize_terms_payload(payload):
    return json.dumps(payload, ensure_ascii=False, indent=2)


class TechnicalTermsManager:
    def __init__(
        self,
        *,
        get_terms_path,
        get_logger,
        normalize_name,
        short_text,
        default_payload_factory,
        get_custom_terms_path=None,
    ):
        self._get_terms_path = get_terms_path
        self._get_logger = get_logger
        self._normalize_name = normalize_name
        self._short_text = short_text
        self._default_payload_factory = default_payload_factory
        self._get_custom_terms_path = get_custom_terms_path
        self._active_modes = tuple()
        self._cache_key = None
        self._payload = None
        self._resolved_terms_cache = {}

    def default_content(self):
        return serialize_terms_payload(self._default_payload_factory())

    @staticmethod
    def _path_cache_key(path):
        if path is None:
            return None
        try:
            stat = path.stat()
            return (str(path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (str(path), None, None)

    def _cache_key_for_paths(self):
        custom_path = self._get_custom_terms_path() if self._get_custom_terms_path else None
        return (
            self._path_cache_key(self._get_terms_path()),
            self._path_cache_key(custom_path),
        )

    def _normalize_mapping(self, raw_mapping):
        normalized = {}
        if isinstance(raw_mapping, dict):
            for raw_key, raw_value in raw_mapping.items():
                key = self._normalize_name(raw_key)
                value = " ".join(str(raw_value or "").split())
                if key and value:
                    normalized[key] = value
        return normalized

    def _load_custom_replacements(self):
        if self._get_custom_terms_path is None:
            return {}, None, tuple()

        path = self._get_custom_terms_path()
        if not path.exists():
            return {}, str(path), tuple()

        replacements = {}
        invalid_lines = []
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except Exception:
            logger = self._get_logger()
            if logger is not None:
                logger.exception("Failed to load custom terms from %s", path)
            return {}, str(path), tuple()

        for line_number, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            source, separator, target = line.partition("=")
            key = self._normalize_name(source)
            value = " ".join(target.split())
            if (
                not separator
                or not key
                or not value
                or len(key) > MAX_CUSTOM_TERM_LENGTH
                or len(value) > MAX_CUSTOM_TERM_LENGTH
                or len(replacements) >= MAX_CUSTOM_TERM_RULES
            ):
                invalid_lines.append(line_number)
                continue
            replacements[key] = value

        if invalid_lines:
            logger = self._get_logger()
            if logger is not None:
                logger.warning(
                    "Ignored invalid custom term lines. path=%s lines=%s",
                    path,
                    ",".join(str(number) for number in invalid_lines),
                )
        return replacements, str(path), tuple(invalid_lines)

    def load(self, force=False):
        cache_key = self._cache_key_for_paths()
        if not force and cache_key == self._cache_key and self._payload is not None:
            return self._payload

        payload = self._default_payload_factory()
        source = "built-in defaults"
        terms_path = self._get_terms_path()

        if terms_path.exists():
            try:
                loaded = json.loads(terms_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
                    source = str(terms_path)
                else:
                    raise ValueError("Technical terms file must contain a JSON object.")
            except Exception:
                logger = self._get_logger()
                if logger is not None:
                    logger.exception(
                        "Failed to load technical terms from %s, using defaults",
                        terms_path,
                    )

        enabled = bool(payload.get("enabled", True))
        global_replacements = self._normalize_mapping(payload.get("replacements", {}))
        modes = {}

        raw_modes = payload.get("modes", {})
        if isinstance(raw_modes, dict):
            for raw_mode_name, raw_mode_payload in raw_modes.items():
                mode_name = " ".join(str(raw_mode_name or "").strip().split())
                if not mode_name or not isinstance(raw_mode_payload, dict):
                    continue

                replacements = self._normalize_mapping(raw_mode_payload.get("replacements", {}))
                modes[mode_name] = {
                    "label": " ".join(str(raw_mode_payload.get("label") or mode_name).split()),
                    "description": " ".join(str(raw_mode_payload.get("description") or "").split()),
                    "replacements": replacements,
                    "term_count": len(replacements),
                }

        custom_replacements, custom_source, invalid_custom_lines = (
            self._load_custom_replacements()
        )

        self._cache_key = cache_key
        self._payload = {
            "enabled": enabled,
            "replacements": global_replacements,
            "modes": modes,
            "source": source,
            "custom_replacements": custom_replacements,
            "custom_term_count": len(custom_replacements),
            "custom_source": custom_source,
            "invalid_custom_lines": invalid_custom_lines,
        }
        self._resolved_terms_cache = {}

        logger = self._get_logger()
        if logger is not None:
            logger.info(
                "Technical terms loaded. enabled=%s global_terms=%s custom_terms=%s modes=%s source=%s custom_source=%s",
                enabled,
                len(global_replacements),
                len(custom_replacements),
                {name: info["term_count"] for name, info in modes.items()},
                source,
                custom_source,
            )
        return self._payload

    def get_available_modes(self):
        return self.load().get("modes", {})

    def set_active_modes(self, modes):
        available = self.get_available_modes()
        normalized = []
        for raw_mode in modes or ():
            mode_name = " ".join(str(raw_mode or "").strip().split())
            if mode_name and mode_name in available and mode_name not in normalized:
                normalized.append(mode_name)
        self._active_modes = tuple(normalized)
        return self._active_modes

    def get_active_modes(self):
        return self._active_modes

    def resolve_active_terms(self, active_modes=None):
        payload = self.load()
        if not payload.get("enabled", True):
            return {}, None

        mode_names = tuple(active_modes if active_modes is not None else self.get_active_modes())
        if mode_names in self._resolved_terms_cache:
            return self._resolved_terms_cache[mode_names]

        combined = dict(payload.get("replacements", {}))
        for mode_name in mode_names:
            mode_payload = payload.get("modes", {}).get(mode_name)
            if mode_payload:
                combined.update(mode_payload.get("replacements", {}))
        combined.update(payload.get("custom_replacements", {}))

        if not combined:
            resolved = ({}, None)
            self._resolved_terms_cache[mode_names] = resolved
            return resolved

        variants = sorted(combined, key=len, reverse=True)
        pattern = re.compile(
            r"(?<!\w)(" + "|".join(re.escape(item) for item in variants) + r")(?!\w)",
            re.IGNORECASE,
        )
        resolved = (combined, pattern)
        self._resolved_terms_cache[mode_names] = resolved
        return resolved

    def apply(self, text, log_changes=False, active_modes=None):
        normalized = " ".join((text or "").split())
        if not normalized:
            return ""

        replacements, pattern = self.resolve_active_terms(active_modes=active_modes)
        if not replacements or pattern is None:
            return normalized

        def repl(match):
            key = self._normalize_name(match.group(0))
            return replacements.get(key, match.group(0))

        corrected = pattern.sub(repl, normalized)
        if log_changes and corrected != normalized:
            logger = self._get_logger()
            if logger is not None:
                active = list(active_modes if active_modes is not None else self.get_active_modes())
                logger.info(
                    "Technical replacements applied. modes=%s before=%s after=%s",
                    active,
                    self._short_text(normalized, 200),
                    self._short_text(corrected, 200),
                )
        return corrected
