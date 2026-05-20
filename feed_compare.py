#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


DEFAULT_NUMERIC_TOLERANCE = 1.0e-6


class FeedCompareError(Exception):
    """Raised when input validation or comparison setup fails."""


@dataclass(frozen=True)
class FieldComparisonRule:
    field_type: str = "string"
    case_sensitive: bool = True
    tolerance: float = DEFAULT_NUMERIC_TOLERANCE


@dataclass(frozen=True)
class Config:
    key_fields: Tuple[str, ...]
    field_rules: Dict[str, FieldComparisonRule]


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two CSV feeds and produce match/mismatch reports."
    )
    parser.add_argument("--feed-a", required=True, help="Path to feed A CSV file")
    parser.add_argument("--feed-b", required=True, help="Path to feed B CSV file")
    parser.add_argument("--conf", required=True, help="Path to JSON config file")
    parser.add_argument(
        "--out-dir", required=True, help="Directory where reports will be written"
    )
    return parser.parse_args(argv)


def load_config(path: Path) -> Config:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FeedCompareError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FeedCompareError(f"Invalid JSON config in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise FeedCompareError("Config root must be a JSON object")

    key_fields = raw.get("key_fields")
    if not isinstance(key_fields, list) or not key_fields or not all(
        isinstance(item, str) and item for item in key_fields
    ):
        raise FeedCompareError("Config key_fields must be a non-empty list of strings")

    raw_rules = raw.get("fields", {})
    if raw_rules is None:
        raw_rules = {}
    if not isinstance(raw_rules, dict):
        raise FeedCompareError("Config fields must be an object when provided")

    field_rules: Dict[str, FieldComparisonRule] = {}
    for field_name, rule_data in raw_rules.items():
        if not isinstance(field_name, str) or not field_name:
            raise FeedCompareError("Field rule names must be non-empty strings")
        if not isinstance(rule_data, dict):
            raise FeedCompareError(f"Rule for field {field_name!r} must be an object")

        field_type = rule_data.get("type", "string")
        if field_type not in {"string", "number"}:
            raise FeedCompareError(
                f"Unsupported comparison type for field {field_name!r}: {field_type!r}"
            )

        case_sensitive = rule_data.get("case_sensitive", True)
        tolerance = rule_data.get("tolerance", DEFAULT_NUMERIC_TOLERANCE)

        if field_type == "string":
            if not isinstance(case_sensitive, bool):
                raise FeedCompareError(
                    f"case_sensitive for field {field_name!r} must be boolean"
                )
            field_rules[field_name] = FieldComparisonRule(
                field_type="string",
                case_sensitive=case_sensitive,
                tolerance=DEFAULT_NUMERIC_TOLERANCE,
            )
            continue

        if not isinstance(tolerance, (int, float)) or tolerance < 0:
            raise FeedCompareError(
                f"tolerance for field {field_name!r} must be a non-negative number"
            )
        field_rules[field_name] = FieldComparisonRule(
            field_type="number",
            case_sensitive=True,
            tolerance=float(tolerance),
        )

    return Config(key_fields=tuple(key_fields), field_rules=field_rules)


def load_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise FeedCompareError(f"CSV file {path} does not contain a header row")

            fieldnames = list(reader.fieldnames)
            rows = []
            for row in reader:
                if row is None:
                    continue
                rows.append({field: row.get(field, "") for field in fieldnames})
    except FileNotFoundError as exc:
        raise FeedCompareError(f"CSV file not found: {path}") from exc

    return fieldnames, rows


def validate_fields(
    fields_a: Sequence[str], fields_b: Sequence[str], config: Config
) -> List[str]:
    if list(fields_a) != list(fields_b):
        raise FeedCompareError(
            "Feed columns are not compatible. "
            f"feed-a columns={list(fields_a)!r}, feed-b columns={list(fields_b)!r}"
        )

    fieldnames = list(fields_a)
    missing_key_fields = [field for field in config.key_fields if field not in fieldnames]
    if missing_key_fields:
        raise FeedCompareError(
            f"Key fields missing in feed columns: {', '.join(missing_key_fields)}"
        )

    unknown_rule_fields = [field for field in config.field_rules if field not in fieldnames]
    if unknown_rule_fields:
        raise FeedCompareError(
            f"Config contains rules for unknown fields: {', '.join(unknown_rule_fields)}"
        )

    return fieldnames


def make_key(row: Dict[str, str], key_fields: Sequence[str]) -> Tuple[str, ...]:
    return tuple(row[field] for field in key_fields)


def index_rows(
    rows: Iterable[Dict[str, str]], key_fields: Sequence[str], feed_label: str
) -> Dict[Tuple[str, ...], Dict[str, str]]:
    indexed: Dict[Tuple[str, ...], Dict[str, str]] = {}
    for row in rows:
        key = make_key(row, key_fields)
        if key in indexed:
            raise FeedCompareError(
                f"Duplicate key detected in {feed_label}: {key!r}"
            )
        indexed[key] = row
    return indexed


def rows_equal(
    row_a: Dict[str, str],
    row_b: Dict[str, str],
    fieldnames: Sequence[str],
    config: Config,
) -> bool:
    for field in fieldnames:
        rule = config.field_rules.get(field, FieldComparisonRule())
        if not values_equal(row_a[field], row_b[field], rule, field):
            return False
    return True


def values_equal(value_a: str, value_b: str, rule: FieldComparisonRule, field: str) -> bool:
    if rule.field_type == "string":
        if rule.case_sensitive:
            return value_a == value_b
        return value_a.casefold() == value_b.casefold()

    try:
        number_a = float(value_a)
        number_b = float(value_b)
    except ValueError as exc:
        raise FeedCompareError(
            f"Field {field!r} is configured as number but contains non-numeric data: "
            f"{value_a!r}, {value_b!r}"
        ) from exc

    return math.isclose(number_a, number_b, abs_tol=rule.tolerance, rel_tol=0.0)


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def compare_feeds(
    feed_a_path: Path, feed_b_path: Path, config: Config, out_dir: Path
) -> None:
    fields_a, rows_a = load_csv(feed_a_path)
    fields_b, rows_b = load_csv(feed_b_path)
    fieldnames = validate_fields(fields_a, fields_b, config)

    indexed_a = index_rows(rows_a, config.key_fields, "feed-a")
    indexed_b = index_rows(rows_b, config.key_fields, "feed-b")

    missing_a: List[Dict[str, str]] = []
    missing_b: List[Dict[str, str]] = []
    matches: List[Dict[str, str]] = []
    mismatch_a: List[Dict[str, str]] = []
    mismatch_b: List[Dict[str, str]] = []
    mismatch_joined: List[Dict[str, str]] = []

    for row_a in rows_a:
        key = make_key(row_a, config.key_fields)
        row_b = indexed_b.get(key)
        if row_b is None:
            missing_a.append(row_a)
            continue
        if rows_equal(row_a, row_b, fieldnames, config):
            matches.append(row_a)
            continue

        mismatch_a.append(row_a)
        mismatch_b.append(row_b)
        mismatch_joined.append(
            {
                **{f"a_{field}": row_a[field] for field in fieldnames},
                **{f"b_{field}": row_b[field] for field in fieldnames},
            }
        )

    for row_b in rows_b:
        key = make_key(row_b, config.key_fields)
        if key not in indexed_a:
            missing_b.append(row_b)

    out_dir.mkdir(parents=True, exist_ok=True)

    feed_a_name = feed_a_path.stem
    feed_b_name = feed_b_path.stem

    write_csv(out_dir / f"{feed_a_name}-missing.csv", fieldnames, missing_a)
    write_csv(out_dir / f"{feed_b_name}-missing.csv", fieldnames, missing_b)
    write_csv(out_dir / "match.csv", fieldnames, matches)
    write_csv(out_dir / f"{feed_a_name}-mismatch.csv", fieldnames, mismatch_a)
    write_csv(out_dir / f"{feed_b_name}-mismatch.csv", fieldnames, mismatch_b)
    joined_fieldnames = [f"a_{field}" for field in fieldnames] + [
        f"b_{field}" for field in fieldnames
    ]
    write_csv(out_dir / "mismatch-joined.csv", joined_fieldnames, mismatch_joined)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        config = load_config(Path(args.conf))
        compare_feeds(
            Path(args.feed_a),
            Path(args.feed_b),
            config,
            Path(args.out_dir),
        )
    except FeedCompareError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
