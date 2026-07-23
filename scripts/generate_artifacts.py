"""Generate reproducible demo artifacts and PNG architecture diagrams."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lineage_guard.engine import analyze_workflow  # noqa: E402

BG = "#081019"
SURFACE = "#101e2b"
LINE = "#294150"
TEXT = "#edf6f7"
MUTED = "#91a9b6"
MINT = "#6df0c2"
CYAN = "#58c7f3"
AMBER = "#ffbc66"


def font(size: int, bold: bool = False):
    names = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for name in names:
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def box(draw: ImageDraw.ImageDraw, xy, title: str, subtitle: str, accent=MINT):
    draw.rounded_rectangle(xy, radius=18, fill=SURFACE, outline=LINE, width=2)
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle((x1, y1, x1 + 8, y2), radius=4, fill=accent)
    draw.text((x1 + 30, y1 + 27), title, font=font(25, True), fill=TEXT)
    draw.multiline_text((x1 + 30, y1 + 67), subtitle, font=font(16), fill=MUTED, spacing=7)


def arrow(draw: ImageDraw.ImageDraw, start, end, label: str = ""):
    draw.line((start, end), fill=CYAN, width=4)
    ex, ey = end
    draw.polygon([(ex, ey), (ex - 13, ey - 8), (ex - 13, ey + 8)], fill=CYAN)
    if label:
        sx, sy = start
        draw.text(((sx + ex) // 2 - 45, sy - 28), label, font=font(13, True), fill=CYAN)


def architecture_diagram(path: Path):
    image = Image.new("RGB", (1600, 900), BG)
    draw = ImageDraw.Draw(image)
    draw.text((70, 54), "Workflow Lineage Guard", font=font(38, True), fill=TEXT)
    draw.text((70, 105), "Evidence-first agent architecture", font=font(20), fill=MUTED)
    box(
        draw,
        (70, 220, 350, 430),
        "Web app",
        "Schema proposal\nn8n workflow JSON\nwrite-back approval",
        MINT,
    )
    box(
        draw,
        (475, 155, 845, 365),
        "OpenAI Agent",
        "Plans the investigation\nCalls MCP + local tools\nExplains verified evidence",
        CYAN,
    )
    box(
        draw,
        (475, 500, 845, 710),
        "Deterministic engine",
        "Schema diff\nExact JSON pointers\nConservative patch",
        AMBER,
    )
    box(
        draw,
        (970, 155, 1450, 365),
        "DataHub MCP",
        "search · list_schema_fields\nget_lineage · paths\nupdate_description (approved)",
        MINT,
    )
    box(
        draw,
        (970, 500, 1450, 710),
        "Context graph",
        "Schemas + column lineage\nOwners + documentation\nInherited risk evidence",
        CYAN,
    )
    arrow(draw, (350, 320), (475, 260), "request")
    arrow(draw, (845, 260), (970, 260), "MCP tools")
    arrow(draw, (660, 365), (660, 500), "exact scan")
    arrow(draw, (1210, 365), (1210, 500), "read/write")
    draw.text(
        (70, 820),
        "Mutations require two gates: server enablement + explicit user approval.",
        font=font(18, True),
        fill=AMBER,
    )
    image.save(path)


def sequence_diagram(path: Path):
    image = Image.new("RGB", (1600, 900), BG)
    draw = ImageDraw.Draw(image)
    draw.text((70, 54), "Impact scan sequence", font=font(38, True), fill=TEXT)
    actors = [(150, "User"), (520, "Guard agent"), (900, "DataHub MCP"), (1310, "Repair engine")]
    for x, name in actors:
        draw.rounded_rectangle(
            (x - 105, 145, x + 105, 205), radius=14, fill=SURFACE, outline=LINE, width=2
        )
        draw.text((x - 70, 164), name, font=font(18, True), fill=TEXT)
        draw.line((x, 205, x, 790), fill=LINE, width=2)
    events = [
        (270, 150, 520, "schema change + workflow"),
        (355, 520, 900, "verify schema + lineage"),
        (440, 900, 520, "trusted context"),
        (525, 520, 1310, "inspect exact references"),
        (610, 1310, 520, "risk + safe JSON patch"),
        (695, 520, 900, "approved write-back"),
        (770, 520, 150, "verdict + evidence"),
    ]
    for y, x1, x2, label in events:
        direction = 1 if x2 > x1 else -1
        draw.line((x1, y, x2, y), fill=CYAN if direction == 1 else MINT, width=3)
        draw.polygon(
            [(x2, y), (x2 - 12 * direction, y - 7), (x2 - 12 * direction, y + 7)],
            fill=CYAN if direction == 1 else MINT,
        )
        text_x = min(x1, x2) + abs(x2 - x1) // 2 - 90
        draw.rectangle((text_x - 8, y - 28, text_x + 205, y - 5), fill=BG)
        draw.text((text_x, y - 27), label, font=font(13, True), fill=MUTED)
    image.save(path)


def main():
    demo = json.loads((ROOT / "data" / "demo_request.json").read_text())
    report = analyze_workflow(
        demo["workflow"],
        demo["current_schema"],
        demo["proposed_schema"],
        dataset_urn=demo["dataset_urn"],
        rename_map=demo["rename_map"],
        lineage_path=demo["lineage_path"],
    ).to_dict()
    examples = ROOT / "examples"
    examples.mkdir(exist_ok=True)
    (examples / "before_workflow.json").write_text(json.dumps(demo["workflow"], indent=2) + "\n")
    (examples / "fixed_workflow.json").write_text(
        json.dumps(report["fixed_workflow"], indent=2) + "\n"
    )
    (examples / "demo_report.json").write_text(json.dumps(report, indent=2) + "\n")
    architecture_diagram(ROOT / "docs" / "agent-interactions.png")
    sequence_diagram(ROOT / "docs" / "agent-sequence.png")
    print("Generated demo JSON and two PNG diagrams.")


if __name__ == "__main__":
    main()
