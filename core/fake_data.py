import random
import re
from datetime import datetime, timedelta

from faker import Faker

_LOCALES = ["en_IN", "en_US"]


def fake_replacement(entity_type: str, seed: str, original: str | None = None) -> str:
    """Generate a natural fictional replacement as a last-resort fallback."""
    faker = Faker(_LOCALES)
    faker.seed_instance(_stable_seed(entity_type, seed))
    entity = (entity_type or "PII").upper()
    source = original or seed

    if entity == "PERSON":
        return faker.name()
    if entity == "EMAIL":
        return faker.email()
    if entity == "PHONE":
        return _same_digit_shape(source, faker)
    if entity == "ADDRESS":
        return faker.address().replace("\n", ", ")
    if entity == "ORGANIZATION":
        return faker.company()
    if entity == "LOCATION":
        return faker.city()
    if entity == "DATE":
        return _shift_date(source, faker)
    if entity == "MONEY":
        return _scale_money(source, faker)
    if entity == "SSN":
        return _same_digit_shape(source, faker)
    if entity == "CREDIT_CARD":
        return _same_digit_shape(source, faker)
    if entity == "ID_NUMBER":
        return _same_id_shape(source, faker)
    if entity == "USERNAME":
        return faker.user_name()
    if entity == "URL":
        return faker.url()
    if entity == "AGE":
        return str(faker.random_int(min=18, max=80))
    return faker.word()


def _stable_seed(entity_type: str, seed: str) -> int:
    value = f"{entity_type}:{seed}"
    rng = random.Random(value)
    return rng.randrange(1, 2**32)


def _same_digit_shape(value: str, faker: Faker) -> str:
    """Replace digits while keeping punctuation/spacing shape."""
    if not any(ch.isdigit() for ch in value):
        return faker.phone_number()
    keep_until = 0
    if value.startswith("+"):
        match = re.match(r"^\+\d+", value)
        keep_until = match.end() if match else 0
    replace_count = sum(ch.isdigit() for index, ch in enumerate(value) if index >= keep_until)
    digits = iter(str(faker.random_int(min=0, max=9)) for _ in range(replace_count))
    return "".join(
        next(digits) if ch.isdigit() and index >= keep_until else ch
        for index, ch in enumerate(value)
    )


def _same_id_shape(value: str, faker: Faker) -> str:
    if not value:
        return faker.bothify(text="??-########")
    chars: list[str] = []
    for ch in value:
        if ch.isdigit():
            chars.append(str(faker.random_int(min=0, max=9)))
        elif ch.isalpha():
            letter = faker.random_uppercase_letter()
            chars.append(letter if ch.isupper() else letter.lower())
        else:
            chars.append(ch)
    return "".join(chars)


def _shift_date(value: str, faker: Faker) -> str:
    offset = timedelta(days=faker.random_int(min=14, max=120))
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"]
    for fmt in formats:
        try:
            return (datetime.strptime(value, fmt) + offset).strftime(fmt)
        except ValueError:
            continue
    return faker.date()


def _scale_money(value: str, faker: Faker) -> str:
    match = re.search(r"(?P<prefix>[$₹€£]?\s*)(?P<num>\d[\d,]*(?:\.\d+)?)(?P<suffix>\s*(?:USD|INR|EUR|GBP|dollars|rupees)?)", value, re.IGNORECASE)
    if not match:
        return f"${faker.random_int(min=50, max=9000):,}"
    number = float(match.group("num").replace(",", ""))
    factor = faker.random_int(min=80, max=120) / 100
    scaled = max(1, number * factor)
    decimals = len(match.group("num").split(".", 1)[1]) if "." in match.group("num") else 0
    formatted = f"{scaled:,.{decimals}f}"
    return f"{match.group('prefix')}{formatted}{match.group('suffix')}"
