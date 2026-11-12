"""Small offline Roman Urdu fallback; lexical overrides improve readability."""
from __future__ import annotations

import re

WORDS = {
    "میں": "mein", "ہے": "hai", "ہیں": "hain", "نہیں": "nahin",
    "اور": "aur", "آپ": "aap", "ہم": "hum", "یہ": "yeh", "وہ": "woh",
    "کا": "ka", "کی": "ki", "کے": "ke", "کو": "ko", "سے": "se",
    "پر": "par", "بھی": "bhi", "تو": "to", "جو": "jo", "کیا": "kya",
    "ایک": "aik", "آج": "aaj", "دوستو": "dosto", "دوستوں": "doston",
    "کر": "kar", "رہے": "rahe", "رہی": "rahi", "کرتے": "karte",
    "اردو": "Urdu", "رومن": "Roman", "انگلش": "English",
    "آٹو": "auto", "کیپشن": "caption", "ٹول": "tool", "ٹیسٹ": "test",
    "بالکل": "bilkul", "فری": "free", "میں": "mein", "السلام": "assalam",
    "سلام": "salaam", "علیکم": "alaikum", "نیا": "naya", "نئی": "nayi",
    "دونوں": "dono", "لئے": "liye", "لیے": "liye", "ٹرانسکرائب": "transcribe",
}
CHARS = {
    "ا": "a", "آ": "aa", "ب": "b", "پ": "p", "ت": "t", "ٹ": "t",
    "ث": "s", "ج": "j", "چ": "ch", "ح": "h", "خ": "kh", "د": "d",
    "ڈ": "d", "ذ": "z", "ر": "r", "ڑ": "r", "ز": "z", "ژ": "zh",
    "س": "s", "ش": "sh", "ص": "s", "ض": "z", "ط": "t", "ظ": "z",
    "ع": "", "غ": "gh", "ف": "f", "ق": "q", "ک": "k", "گ": "g",
    "ل": "l", "م": "m", "ن": "n", "ں": "n", "و": "o", "ہ": "h",
    "ھ": "h", "ء": "", "ی": "i", "ے": "e", "ئ": "i", "ؤ": "o",
}
TOKEN = re.compile(r"[\u0600-\u06ff]+|[^\u0600-\u06ff]+")


def romanize(text: str) -> str:
    """Romanize Arabic-script Urdu and leave Latin text and punctuation intact."""
    def convert(token: str) -> str:
        if not token or not ("\u0600" <= token[0] <= "\u06ff"):
            return token
        return WORDS.get(token, "".join(CHARS.get(c, "") for c in token))
    return "".join(convert(part) for part in TOKEN.findall(text))
