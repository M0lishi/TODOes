"""Цвета и константы оформления (пастельная палитра в стиле iOS)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    key: str
    title: str
    bg: str      # фон стикера
    accent: str  # цвет галочек и акцентов


PALETTES = [
    Palette("yellow", "Жёлтый", "#FFF1A8", "#E5B800"),
    Palette("pink", "Розовый", "#FFD4E1", "#EE6A92"),
    Palette("blue", "Голубой", "#CFE6FF", "#3D8FE0"),
    Palette("green", "Зелёный", "#D3F3CF", "#4DB35A"),
    Palette("purple", "Сиреневый", "#E3D8FF", "#8F6DE3"),
    Palette("peach", "Персиковый", "#FFE0C4", "#F28C3D"),
]
BY_KEY = {p.key: p for p in PALETTES}

# Системные цвета iOS
INK = "#1C1C1E"
INK_SECONDARY = "rgba(60, 60, 67, 75%)"
IOS_BLUE = "#007AFF"
IOS_RED = "#FF3B30"
IOS_ORANGE = "#FF9500"

FONT_FAMILIES = [
    "SF Pro Text", ".AppleSystemUIFont", "Segoe UI Variable", "Segoe UI",
    "Helvetica Neue", "Ubuntu", "Noto Sans", "sans-serif",
]
