import csv
from datetime import datetime, timezone
from pathlib import Path


RAW_FILE = Path("data/mes_sep26_1min_1month_raw.txt")
OUTPUT_FILE = Path("data/mes_sep26_1min_1month_bot.csv")

def convert_ninjatrader_file(raw_file: Path, output_file: Path) -> None:
    if not raw_file.exists():
        raise FileNotFoundError(f"Raw file not found: {raw_file}")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    rows_written = 0
    rows_skipped = 0

    with raw_file.open("r", encoding="utf-8") as infile, output_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )

        writer.writeheader()

        for line_number, line in enumerate(infile, start=1):
            clean_line = line.strip()

            if not clean_line:
                rows_skipped += 1
                continue

            parts = clean_line.split(";")

            if len(parts) != 6:
                print(f"Skipping line {line_number}: expected 6 fields, got {len(parts)}")
                rows_skipped += 1
                continue

            timestamp_text, open_text, high_text, low_text, close_text, volume_text = parts

            try:
                timestamp = datetime.strptime(timestamp_text, "%Y%m%d %H%M%S")
                timestamp = timestamp.replace(tzinfo=timezone.utc)

                writer.writerow(
                    {
                        "timestamp": timestamp.isoformat(),
                        "open": float(open_text),
                        "high": float(high_text),
                        "low": float(low_text),
                        "close": float(close_text),
                        "volume": int(float(volume_text)),
                    }
                )

                rows_written += 1

            except ValueError as error:
                print(f"Skipping line {line_number}: {error}")
                rows_skipped += 1

    print("Conversion complete.")
    print(f"Raw file: {raw_file}")
    print(f"Output file: {output_file}")
    print(f"Rows written: {rows_written}")
    print(f"Rows skipped: {rows_skipped}")


if __name__ == "__main__":
    convert_ninjatrader_file(RAW_FILE, OUTPUT_FILE)