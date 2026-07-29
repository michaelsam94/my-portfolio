"""Build browser-searchable result shards from the Thanaweya Amma workbook."""

from collections import defaultdict
import json
from pathlib import Path
import re
import shutil
import sys
from zipfile import ZipFile
from xml.etree.ElementTree import iterparse

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
ARABIC_MARKS = re.compile(r"[\u064b-\u065f\u0670\u06d6-\u06ed]")


def normalize_name(value: str) -> str:
    value = ARABIC_MARKS.sub("", value)
    value = value.translate(
        str.maketrans(
            {
                "أ": "ا",
                "إ": "ا",
                "آ": "ا",
                "ى": "ي",
                "ؤ": "و",
                "ئ": "ي",
                "ة": "ه",
                "ـ": "",
            }
        )
    )
    return " ".join(value.split()).strip()


def cell_value(cell, shared_strings: list[str]) -> str:
    value = cell.find(f"{NS}v")
    raw = value.text if value is not None and value.text is not None else ""
    if cell.attrib.get("t") == "s" and raw:
        return shared_strings[int(raw)]
    return raw


def build(source: Path, output: Path) -> None:
    with ZipFile(source) as archive:
        shared_strings: list[str] = []
        with archive.open("xl/sharedStrings.xml") as stream:
            for _, element in iterparse(stream, events=("end",)):
                if element.tag == f"{NS}si":
                    shared_strings.append(
                        "".join(node.text or "" for node in element.iter(f"{NS}t"))
                    )
                    element.clear()

        name_shards: dict[str, list[list[str]]] = defaultdict(list)
        seat_shards: dict[str, list[list[str]]] = defaultdict(list)
        score_counts: dict[str, int] = defaultdict(int)
        row_count = 0

        with archive.open("xl/worksheets/sheet1.xml") as stream:
            for _, element in iterparse(stream, events=("end",)):
                if element.tag != f"{NS}row":
                    continue

                cells = [
                    cell_value(cell, shared_strings)
                    for cell in element.findall(f"{NS}c")
                ]
                element.clear()

                if not cells or cells[0] == "seating_no" or len(cells) < 4:
                    continue

                seat, name, total, status = cells[:4]
                normalized = normalize_name(name)
                if not seat or not normalized:
                    continue

                record = [seat, name, total, status]
                name_shards[normalized[0]].append(record)
                seat_shards[seat[:3]].append(record)
                score_counts[total] += 1
                row_count += 1

    staging = output.with_name(f"{output.name}-staging")
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "names").mkdir(parents=True)
    (staging / "seats").mkdir()

    compact = {"ensure_ascii": False, "separators": (",", ":")}
    for key, records in name_shards.items():
        records.sort(key=lambda record: (normalize_name(record[1]), record[0]))
        (staging / "names" / f"{ord(key):x}.json").write_text(
            json.dumps(records, **compact), encoding="utf-8"
        )

    for key, records in seat_shards.items():
        records.sort(key=lambda record: record[0])
        (staging / "seats" / f"{key}.json").write_text(
            json.dumps(records, **compact), encoding="utf-8"
        )

    score_stats = {}
    higher_students = 0
    for dense_index, (score, count) in enumerate(
        sorted(score_counts.items(), key=lambda item: float(item[0]), reverse=True),
        start=1,
    ):
        score_stats[score] = {
            "rankWithRepetition": higher_students + 1,
            "rankWithoutRepetition": dense_index,
            "sameScoreCount": count,
        }
        higher_students += count

    manifest = {
        "count": row_count,
        "nameShards": {key: f"{ord(key):x}" for key in sorted(name_shards)},
        "seatPrefixes": sorted(seat_shards),
        "scoreStats": score_stats,
    }
    (staging / "manifest.json").write_text(
        json.dumps(manifest, **compact), encoding="utf-8"
    )

    if output.exists():
        shutil.rmtree(output)
    staging.rename(output)
    print(f"Built {row_count:,} result records in {output}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: build-natega-data.py SOURCE.xlsx OUTPUT_DIR")
    build(Path(sys.argv[1]), Path(sys.argv[2]))
