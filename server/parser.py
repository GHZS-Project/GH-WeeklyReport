import argparse
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
SUMMARY_HEADERS = ["日期", "活跃", "注册值", "支付金额", "活跃ARPU", "付费ARPU", "付费人数", "活跃付费率", "收益"]

def text(value): return "" if value is None else str(value).replace("\n", " ").strip()
def number(value):
    try: return float(text(value).replace(",", "").replace("%", ""))
    except ValueError: return None
def col_index(label):
    out = 0
    for char in label: out = out * 26 + ord(char.upper()) - 64
    return out

def read_book(file_path):
    with zipfile.ZipFile(file_path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_map = {item.attrib["Id"]: item.attrib["Target"] for item in rels}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//a:t", NS)) for item in root.findall("a:si", NS)]
        sheets = {}
        for sheet in workbook.findall("a:sheets/a:sheet", NS):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = "xl/" + rel_map[rel_id].lstrip("/")
            root = ET.fromstring(archive.read(target))
            rows = []
            for row_node in root.findall("a:sheetData/a:row", NS):
                row = {}
                for cell in row_node.findall("a:c", NS):
                    ref = cell.attrib.get("r", "")
                    col = col_index("".join(ch for ch in ref if ch.isalpha()))
                    node = cell.find("a:v", NS)
                    if cell.attrib.get("t") == "s" and node is not None: value = shared[int(node.text)]
                    elif cell.attrib.get("t") == "inlineStr": value = "".join(item.text or "" for item in cell.findall(".//a:t", NS))
                    else: value = node.text if node is not None else ""
                    row[col] = text(value)
                rows.append(row)
            sheets[name] = rows
    return sheets

def find_sheet(sheets, keyword):
    return next((rows for name, rows in sheets.items() if keyword in name), [])

def display(value, header=""):
    value = text(value)
    n = number(value)
    if n is None: return value
    if "率" in header or "%" in value:
        return f"{n * 100 if n <= 1 else n:.2f}%"
    if header == "付费人数": return str(round(n))
    if "ARPU" in header or header in {"收益", "支付金额", "注册值", "流水", "平均收益", "日均流水", "日均收益", "分成后收入"}: return f"{n:.2f}"
    return str(round(n)) if n.is_integer() else f"{n:.2f}"

def section_rows(rows, title, headers=SUMMARY_HEADERS, multiplier=None, limit=5, source_name=""):
    titles = title if isinstance(title, (list, tuple)) else [title]
    start = next((index for index, row in enumerate(rows) if any(marker in value for marker in titles for value in row.values())), None)
    if start is None: return []
    header_row = next((index for index in range(start, min(start + 8, len(rows))) if any("日期" in value for value in rows[index].values())), None)
    if header_row is None: return []
    mapping = {}
    for col, value in rows[header_row].items():
        if value and value not in mapping:
            mapping[value] = col
    records = []
    for row in rows[header_row + 1:]:
        raw_date = text(row.get(mapping.get("日期", -1)))
        if not raw_date: 
            if records: break
            continue
        if any(marker in raw_date for marker in ("总", "日均")): continue
        item = {header: display(row.get(mapping.get(header, -1), ""), header) for header in headers}
        item["日期"] = raw_date
        if multiplier is not None:
            flow = number(row.get(mapping.get("流水", mapping.get("支付金额", -1)), ""))
            item["流水"] = display(flow or 0, "流水")
            item["收益"] = f"{(flow or 0) * multiplier:.2f}"
        records.append(item)
    cutoff = len(records) - 1
    target = re.search(r"(\d{1,2})[.](\d{1,2})-(\d{1,2})[.](\d{1,2})", source_name)
    if target:
        target_month, target_day = int(target.group(3)), int(target.group(4))
        dated = []
        for index, item in enumerate(records):
            match = re.search(r"（\d{1,2}[.]\d{1,2}~(\d{1,2})[.](\d{1,2})", item["日期"])
            if match:
                month, day = int(match.group(1)), int(match.group(2))
                dated.append((abs((month * 32 + day) - (target_month * 32 + target_day)), index))
        if dated: cutoff = min(dated)[1]
    visible = records[:cutoff + 1]
    return visible if limit is None else visible[-limit:]

def summary(rows, limit=5, source_name=""):
    definitions = [
        ("九游CPS", ["九游CPS", "九游-周汇总"], SUMMARY_HEADERS, None), ("801-周汇总", "801-周汇总", SUMMARY_HEADERS, None),
        ("鲸云-周汇总", "鲸云-周汇总", SUMMARY_HEADERS, None), ("穿山甲-收益", "穿山甲-收益", ["日期", "收益"], None),
        ("CPM-收益", "CPM-收益", ["日期", "流水", "收益"], .92), ("DSP-收益", "DSP-收益", ["日期", "流水", "收益"], .92)
    ]
    return [{"title": title, "headers": headers, "rows": section_rows(rows, marker, headers, multiplier, limit, source_name)} for title, marker, headers, multiplier in definitions]

def parse_new_games(rows):
    result, sections = {"网络": [], "福利": []}, []
    marks = {}
    for r, row in enumerate(rows):
        for col, value in row.items():
            if "网游" in value or "网络" in value: marks[col] = "网络"
            elif "福利" in value: marks[col] = "福利"
            elif value in {"游戏", "游戏名", "游戏名称"} and col in marks: sections.append((marks[col], col, r + 1))
    for group, col, start in sections:
        for row in rows[start:]:
            name = text(row.get(col))
            if not name: continue
            if name in {"游戏", "游戏名", "游戏名称", "日均", "总计", "合计"}: continue
            if "福利" in name or "网络" in name or "网游" in name: break
            if name not in result[group]: result[group].append(name)
    return result

def total_detail_table(rows, group, title, limit):
    headers = ["序号", "游戏名", "注册汇总", "付费汇总", "收益汇总", "平均收益"]
    candidates = []
    group_row = rows[0] if rows else {}
    start_col = next((col for col, value in group_row.items() if group in value), None)
    if start_col is None: return {"title": title, "headers": headers, "rows": []}
    for row in rows[2:]:
        name = text(row.get(1))
        if not name: break
        revenue = number(row.get(start_col + 2)) or 0
        candidates.append({"游戏名": name, "注册汇总": display(row.get(start_col), "注册汇总"), "付费汇总": display(row.get(start_col + 1), "付费汇总"), "收益汇总": f"{revenue:.2f}", "平均收益": display(revenue / 7, "平均收益"), "_revenue": revenue})
    candidates.sort(key=lambda item: item["_revenue"], reverse=True)
    for index, item in enumerate(candidates[:limit], 1): item["序号"] = str(index); item.pop("_revenue", None)
    return {"title": title, "headers": headers, "rows": candidates[:limit]}

def welfare_detail_table(rows, limit=15):
    headers = ["序号", "游戏名称", "新增", "支付金额", "分成后收入", "分成比例", "日均新增", "日均流水", "日均收益"]
    candidates = []
    for row in rows[1:]:
        name = text(row.get(1))
        if not name: break
        new_count = number(row.get(3)) or 0
        amount = number(row.get(4)) or 0
        income = number(row.get(5)) or 0
        candidates.append({"游戏名称": name, "新增": display(new_count, "新增"), "支付金额": f"{amount:.2f}", "分成后收入": f"{income:.2f}", "分成比例": f"{(income / amount * 100) if amount else 0:.2f}%", "日均新增": f"{new_count / 7:.2f}", "日均流水": f"{amount / 7:.2f}", "日均收益": f"{income / 7:.2f}", "_revenue": income})
    candidates.sort(key=lambda item: item["_revenue"], reverse=True)
    for index, item in enumerate(candidates[:limit], 1): item["序号"] = str(index); item.pop("_revenue", None)
    return {"title": "福利游戏数据明细", "headers": headers, "rows": candidates[:limit]}

def detail_tables_for_aggregate(rows, welfare):
    headers = ["序号", "游戏名", "注册汇总", "付费汇总", "收益汇总", "平均收益"]
    merged = {}
    for group in ("九游", "腾讯"):
        table = total_detail_table(rows, group, group, None)
        for row in table["rows"]:
            name = text(row.get("游戏名"))
            if not name:
                continue
            target = merged.setdefault(name, {"游戏名": name, "注册汇总": 0.0, "付费汇总": 0.0, "收益汇总": 0.0})
            target["注册汇总"] += number(row.get("注册汇总")) or 0.0
            target["付费汇总"] += number(row.get("付费汇总")) or 0.0
            target["收益汇总"] += number(row.get("收益汇总")) or 0.0
    result = list(merged.values())
    result.sort(key=lambda row: row["收益汇总"], reverse=True)
    for index, row in enumerate(result, 1):
        row["序号"] = str(index)
        row["注册汇总"] = display(row["注册汇总"], "注册汇总")
        row["付费汇总"] = display(row["付费汇总"], "付费汇总")
        row["收益汇总"] = f"{row['收益汇总']:.2f}"
        row["平均收益"] = f"{(number(row['收益汇总']) or 0) / 7:.2f}"
    return [{"title": "游戏详情收益汇总", "headers": headers, "rows": result}]

def report(source_dir, source_name=None, all_weeks=False):
    files = sorted([item for item in Path(source_dir).glob("*.xlsx") if not item.name.startswith("~$")], key=lambda item: item.stat().st_mtime, reverse=True)
    if not files: raise FileNotFoundError("目录中没有 .xlsx 周报文件")
    source = next((item for item in files if item.name == source_name), files[0])
    sheets = read_book(source)
    weekly, archive, total, welfare, new_games = find_sheet(sheets, "周收益"), find_sheet(sheets, "数据存档"), find_sheet(sheets, "总数据"), find_sheet(sheets, "指趣数据"), find_sheet(sheets, "新游")
    summary_rows = archive or weekly
    return {"sourceName": source.name, "sourceFile": str(source), "sourceUpdatedAt": datetime.fromtimestamp(source.stat().st_mtime).isoformat(), "summary": summary(summary_rows, None if all_weeks else 5, source.name), "detail": [total_detail_table(total, "九游", "九游数据明细", 20), total_detail_table(total, "腾讯", "腾讯游戏数据明细", 12), welfare_detail_table(welfare)], "newGames": parse_new_games(new_games), "meta": {"sheets": list(sheets)}}

def aggregate(source_dir):
    files = sorted([item for item in Path(source_dir).glob("*.xlsx") if not item.name.startswith("~$")], key=lambda item: item.stat().st_mtime, reverse=True)
    merged = {}
    if files:
        latest = report(source_dir, files[0].name, all_weeks=True)["summary"]
        if any(table["rows"] for table in latest):
            return {"modules": latest}
    for file in files:
        for table in report(source_dir, file.name, all_weeks=True)["summary"]:
            target = merged.setdefault(table["title"], {"title": table["title"], "headers": table["headers"], "rows": {}})
            for row in table["rows"]:
                # 文件按修改时间从新到旧扫描，同一周始终保留最新有数据版本。
                target["rows"].setdefault(row["日期"], row)
    return {"modules": [{"title": value["title"], "headers": value["headers"], "rows": list(value["rows"].values())} for value in merged.values()]}

def aggregate_detail(source_dir):
    files = sorted([item for item in Path(source_dir).glob("*.xlsx") if not item.name.startswith("~$")], key=lambda item: item.stat().st_mtime, reverse=True)
    merged = {}
    seen_weeks = set()
    for file in files:
        sheets = read_book(file)
        archive = find_sheet(sheets, "数据存档") or find_sheet(sheets, "周收益")
        total = find_sheet(sheets, "总数据")
        welfare = find_sheet(sheets, "指趣数据")
        week_rows = summary(archive, None, file.name)
        week_keys = [row["日期"] for table in week_rows for row in table["rows"] if row.get("日期")]
        week_key = week_keys[-1] if week_keys else file.name
        if week_key in seen_weeks:
            continue
        seen_weeks.add(week_key)
        for table in detail_tables_for_aggregate(total, welfare):
            target = merged.setdefault(table["title"], {"title": table["title"], "headers": table["headers"], "rows": {}})
            name_key = "游戏名称" if "游戏名称" in table["headers"] else "游戏名"
            for row in table["rows"]:
                name = text(row.get(name_key))
                if not name:
                    continue
                existing = target["rows"].setdefault(name, {name_key: name, "_weeks": 0, "_revenue": 0.0})
                existing["_weeks"] += 1
                if name_key == "游戏名称":
                    for field in ("新增", "支付金额", "分成后收入"):
                        existing[field] = (existing.get(field, 0.0) or 0.0) + (number(row.get(field)) or 0.0)
                    existing["_revenue"] += number(row.get("分成后收入")) or 0.0
                else:
                    for field in ("注册汇总", "付费汇总"):
                        existing[field] = (existing.get(field, 0.0) or 0.0) + (number(row.get(field)) or 0.0)
                    existing["_revenue"] += number(row.get("收益汇总")) or 0.0
    output = []
    for title, table in merged.items():
        rows = list(table["rows"].values())
        headers = table["headers"]
        for row in rows:
            weeks = max(int(row.pop("_weeks", 1)), 1)
            revenue = row.pop("_revenue", 0.0)
            if "游戏名" in headers:
                row["注册汇总"] = display(row.get("注册汇总", 0), "注册汇总")
                row["付费汇总"] = display(row.get("付费汇总", 0), "付费汇总")
                row["收益汇总"] = f"{revenue:.2f}"
                row["平均收益"] = f"{revenue / (7 * weeks):.2f}"
            else:
                amount = row.get("支付金额", 0.0)
                income = row.get("分成后收入", 0.0)
                row["新增"] = display(row.get("新增", 0), "新增")
                row["支付金额"] = f"{amount:.2f}"
                row["分成后收入"] = f"{income:.2f}"
                row["分成比例"] = f"{(income / amount * 100) if amount else 0:.2f}%"
                row["日均新增"] = f"{(number(row['新增']) or 0) / (7 * weeks):.2f}"
                row["日均流水"] = f"{amount / (7 * weeks):.2f}"
                row["日均收益"] = f"{income / (7 * weeks):.2f}"
        rows.sort(key=lambda item: number(item.get("收益汇总", item.get("分成后收入", 0))) or 0, reverse=True)
        for index, row in enumerate(rows, 1): row["序号"] = str(index)
        output.append({"title": title, "headers": headers, "rows": rows})
    return {"modules": output}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("command", choices=["data", "aggregate", "detail-aggregate"]); parser.add_argument("--dir", required=True); parser.add_argument("--file", default=""); args = parser.parse_args()
    if args.command == "data": print(json.dumps(report(args.dir, args.file or None), ensure_ascii=False))
    if args.command == "aggregate": print(json.dumps(aggregate(args.dir), ensure_ascii=False))
    if args.command == "detail-aggregate": print(json.dumps(aggregate_detail(args.dir), ensure_ascii=False))
