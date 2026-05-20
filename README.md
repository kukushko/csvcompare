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
- `match.csv`: rows present in both feeds and equal by all fields.
- `<feed-a-name>-mismatch.csv`: feed A slice for rows with the same key but different values.
- `<feed-b-name>-mismatch.csv`: feed B slice for rows with the same key but different values.
- `mismatch-joined.csv`: joined mismatch rows with `a_` and `b_` prefixes.

## Validation failures

Tool exits with error when:

- CSV column lists differ.
- Config references unknown fields.
- Key fields are absent in feed columns.
- Duplicate keys exist inside one feed.
- A field configured as numeric contains non-numeric data.

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
