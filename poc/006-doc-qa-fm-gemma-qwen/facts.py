"""Key-fact extraction for PoC 006: dates, durations and jurisdictions.

prepare.py uses it on the gold answer spans; summarize.py uses it on the model answers. An answer
gets a key fact right when it contains at least one of the facts found in the gold span. The
patterns are frozen at registration.
"""

import re

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}
_MONTH = "(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
# The ordinal may be split by OCR in CUAD's text ("16t h day of May").
_DAY = r"(\d{1,2})(?:s\s?t|n\s?d|r\s?d|t\s?h)?"
DATE_PATTERNS = [
    # June 21, 1999 / Jun. 21st 1999
    ("mdy", re.compile(rf"\b{_MONTH}\s+{_DAY}\s*,?\s+(\d{{4}})\b", re.I)),
    # 21 June 1999 / 21st day of June, 1999
    ("dmy", re.compile(rf"\b{_DAY}\s+(?:day\s+of\s+)?{_MONTH}\s*,?\s+(\d{{4}})\b", re.I)),
    # 6/21/1999 / 6/21/99 (US order)
    ("slash", re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})\b")),
    # 1999-06-21
    ("iso", re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")),
]


def _valid(y, m, d):
    return 1 <= m <= 12 and 1 <= d <= 31 and 1900 <= y <= 2100


def dates(text):
    """Set of (year, month, day) found in the text."""
    found = set()
    for kind, pattern in DATE_PATTERNS:
        for g in pattern.findall(text):
            if kind == "mdy":
                y, m, d = int(g[2]), MONTHS[g[0].lower()], int(g[1])
            elif kind == "dmy":
                y, m, d = int(g[2]), MONTHS[g[1].lower()], int(g[0])
            elif kind == "slash":
                m, d, y = int(g[0]), int(g[1]), int(g[2])
                if y < 100:
                    y += 1900 if y >= 50 else 2000
            else:
                y, m, d = int(g[0]), int(g[1]), int(g[2])
            if _valid(y, m, d):
                found.add((y, m, d))
    return found


NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "twenty-four": 24, "thirty": 30, "thirty-six": 36, "forty": 40, "forty-five": 45,
    "fifty": 50, "sixty": 60, "seventy-five": 75, "ninety": 90, "one hundred twenty": 120,
    "one hundred eighty": 180, "three hundred sixty-five": 365,
}
_NUMWORD = "(" + "|".join(sorted((re.escape(w) for w in NUMBER_WORDS), key=len, reverse=True)) + ")"
DURATION = re.compile(
    rf"\b(?:(\d+)|{_NUMWORD})\s*(?:\((\d+)\)\s*)?[-\s]?"
    r"(?:(?:calendar|business|consecutive|full|additional|successive)\s+)*"
    r"(day|week|month|year)s?\b",
    re.I,
)


def durations(text):
    """Set of normalized durations: ("d", days) for days and weeks, ("m", months) for months
    and years. "Twelve months" and "one year" are the same duration."""
    found = set()
    for digits, word, paren, unit in DURATION.findall(text):
        if paren:
            n = int(paren)
        elif digits:
            n = int(digits)
        else:
            n = NUMBER_WORDS[word.lower()]
        unit = unit.lower()
        if n <= 0:
            continue
        if unit == "day":
            found.add(("d", n))
        elif unit == "week":
            found.add(("d", n * 7))
        elif unit == "month":
            found.add(("m", n))
        else:
            found.add(("m", n * 12))
    return found


JURISDICTIONS = [
    # US states and DC
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas",
    "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey",
    "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming",
    "District of Columbia",
    # Canadian provinces
    "Alberta", "British Columbia", "Manitoba", "New Brunswick", "Nova Scotia", "Ontario",
    "Quebec", "Saskatchewan",
    # countries and other jurisdictions
    "England", "Wales", "Scotland", "United Kingdom", "Ireland", "Hong Kong", "Singapore",
    "China", "Japan", "Korea", "Taiwan", "India", "Israel", "Germany", "France", "Italy", "Spain",
    "Netherlands", "Switzerland", "Sweden", "Norway", "Denmark", "Finland", "Belgium",
    "Luxembourg", "Austria", "Australia", "New Zealand", "Canada", "Mexico", "Brazil",
    "Cayman Islands", "Bermuda", "British Virgin Islands", "Malaysia", "Thailand", "Philippines",
    "Russia", "Kazakhstan", "Cyprus", "Greece", "Poland", "Turkey", "South Africa",
    "United Arab Emirates", "Vietnam", "Indonesia",
]
_JURIS = [(j, re.compile(rf"\b{re.escape(j)}\b", re.I)) for j in sorted(JURISDICTIONS, key=len, reverse=True)]


def jurisdictions(text):
    """Set of jurisdiction names in the text. Longer names win: "West Virginia" is not also
    counted as "Virginia"."""
    found = set()
    for name, pattern in _JURIS:
        if pattern.search(text):
            found.add(name)
            text = pattern.sub(" ", text)
    return found


def key_facts(kind, text):
    """Facts of one kind in the text, as sorted lists that JSON can store."""
    if kind == "date":
        return sorted(["date", *f] for f in dates(text))
    if kind == "duration":
        return sorted(["duration", *f] for f in durations(text))
    if kind == "date_or_duration":
        return key_facts("date", text) + key_facts("duration", text)
    if kind == "jurisdiction":
        return sorted(["jurisdiction", j] for j in jurisdictions(text))
    raise ValueError(kind)
