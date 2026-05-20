# CSV Feed Compare

CLI tool on `python3` for comparing two CSV feeds by a composite key and producing CSV reports.

## Run

```bash
python3 feed_compare.py \
  --feed-a /path/to/feed-a.csv \
  --feed-b /path/to/feed-b.csv \
  --conf /path/to/config.json \
  --out-dir /path/to/result-dir
```

Example:

```bash
python3 feed_compare.py \
  --feed-a examples/feed-a.csv \
  --feed-b examples/feed-b.csv \
  --conf examples/config.json \
  --out-dir out
```

Before each run the tool deletes all report files it may create in `--out-dir`, so stale outputs from an earlier run are not left behind.

## Config format

```json
{
  "key_fields": ["id"],
  "fields": {
    "name": {
      "type": "string",
      "case_sensitive": false
    },
    "amount": {
      "type": "number",
      "tolerance": 0.000001
    }
  }
}
```

## Rules

- `key_fields` is required and defines the comparison key.
- `fields` is optional.
- Default comparison for every field is string, case-sensitive.
- For `type: "string"` you can override `case_sensitive`.
- For `type: "number"` you can override `tolerance`, default is `1.0e-6`.

## Generated reports

- `<feed-a-name>-missing.csv`: rows present in feed A and absent in feed B.
- `<feed-b-name>-missing.csv`: rows present in feed B and absent in feed A.
- `<feed-a-name>-duplicates-ignored.csv`: all rows from feed A whose key is duplicated inside feed A.
- `<feed-b-name>-duplicates-ignored.csv`: all rows from feed B whose key is duplicated inside feed B.
- `match.csv`: rows present in both feeds and equal by all fields.
- `<feed-a-name>-mismatch.csv`: feed A slice for rows with the same key but different values.
- `<feed-b-name>-mismatch.csv`: feed B slice for rows with the same key but different values.
- `mismatch-joined.csv`: joined mismatch rows with `a_` and `b_` prefixes.

## Validation failures

Tool exits with error when:

- CSV column lists differ.
- Config references unknown fields.
- Key fields are absent in feed columns.
- A field configured as numeric contains non-numeric data.

## Duplicate keys

If a key occurs more than once inside a feed, those rows are excluded from comparison for that feed and written to the corresponding `*-duplicates-ignored.csv` report.
If the same key is duplicated in feed A, no row with that key from feed A participates in `match`, `missing`, or `mismatch`.

## Example data

Directory [examples](/home/hlt/csvcompare/examples) contains:

- `feed-a.csv`
- `feed-b.csv`
- `config.json`

These files cover:

- `match`: row `id=1` matches because `name` is compared case-insensitively and `amount` matches within tolerance.
- `mismatch`: row `id=2` mismatches because `code` is case-sensitive, row `id=5` mismatches because numeric difference exceeds tolerance.
- `missing in B`: row `id=3`.
- `missing in A`: row `id=4`.
- `duplicates ignored`: rows `id=6` in feed A and `id=7` in feed B.
