"""File analysis tools — PDF, CSV/Excel, and image analysis for Miguel.

Provides tools to read and analyze common file formats, making Miguel
useful for real-world data tasks like 'analyze this spreadsheet' or
'summarize this PDF'.
"""

import os
from pathlib import Path
from typing import Optional

from miguel.agent.tools.error_utils import safe_tool, AGENT_DIR


def _resolve_file_path(file_path: str) -> Path:
    """Resolve a file path — handles both absolute and relative paths.
    
    For relative paths, checks multiple locations:
    1. Relative to agent directory
    2. Relative to user files directory
    3. As-is (absolute)
    
    Returns the resolved Path or raises FileNotFoundError.
    """
    p = Path(file_path)
    
    # If absolute and exists, use it directly
    if p.is_absolute() and p.exists():
        return p
    
    # Try relative to agent dir
    agent_path = AGENT_DIR / file_path
    if agent_path.exists():
        return agent_path
    
    # Try user files dir
    from miguel.agent.config import USER_FILES_DIR
    user_path = Path(USER_FILES_DIR) / file_path
    if user_path.exists():
        return user_path
    
    # Try as absolute path one more time
    if p.exists():
        return p
    
    raise FileNotFoundError(
        f"File not found: '{file_path}'. "
        f"Searched in: agent dir ({AGENT_DIR}), user files ({USER_FILES_DIR}), and absolute path."
    )


@safe_tool
def analyze_csv(file_path: str, max_rows: int = 20, query: str = "") -> str:
    """Load and analyze a CSV or Excel file. Shows shape, columns, dtypes, stats, and sample rows.
    
    Args:
        file_path: Path to the CSV/Excel file (absolute or relative to agent/user_files dir).
        max_rows: Maximum number of sample rows to display (default 20).
        query: Optional pandas query string to filter data (e.g. "age > 30", "country == 'US'").
    """
    import pandas as pd
    
    resolved = _resolve_file_path(file_path)
    suffix = resolved.suffix.lower()
    
    # Load the file
    if suffix == ".csv":
        df = pd.read_csv(resolved)
    elif suffix == ".tsv":
        df = pd.read_csv(resolved, sep="\t")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(resolved)
    elif suffix == ".json":
        df = pd.read_json(resolved)
    elif suffix == ".parquet":
        df = pd.read_parquet(resolved)
    else:
        # Try CSV as fallback
        df = pd.read_csv(resolved)
    
    # Apply query filter if provided
    if query:
        try:
            df = df.query(query)
        except Exception as e:
            return f"Error applying query '{query}': {e}\n\nValid columns: {list(df.columns)}"
    
    # Build analysis
    lines = []
    lines.append(f"## File: {resolved.name}")
    lines.append(f"**Path:** {resolved}")
    lines.append(f"**Shape:** {df.shape[0]:,} rows × {df.shape[1]} columns")
    if query:
        lines.append(f"**Filter:** `{query}`")
    lines.append("")
    
    # Column info
    lines.append("### Columns & Types")
    lines.append("| Column | Type | Non-Null | Unique | Sample |")
    lines.append("|--------|------|----------|--------|--------|")
    for col in df.columns:
        dtype = str(df[col].dtype)
        non_null = df[col].notna().sum()
        unique = df[col].nunique()
        sample = str(df[col].dropna().iloc[0]) if non_null > 0 else "N/A"
        if len(sample) > 40:
            sample = sample[:37] + "..."
        lines.append(f"| {col} | {dtype} | {non_null:,} | {unique:,} | {sample} |")
    lines.append("")
    
    # Numeric stats
    numeric_cols = df.select_dtypes(include=["number"]).columns
    if len(numeric_cols) > 0:
        lines.append("### Numeric Statistics")
        stats = df[numeric_cols].describe().round(2)
        lines.append(stats.to_markdown())
        lines.append("")
    
    # Missing data summary
    missing = df.isnull().sum()
    if missing.any():
        lines.append("### Missing Values")
        for col in missing[missing > 0].index:
            pct = (missing[col] / len(df)) * 100
            lines.append(f"- **{col}**: {missing[col]:,} ({pct:.1f}%)")
        lines.append("")
    
    # Sample rows
    display_rows = min(max_rows, len(df))
    lines.append(f"### Sample Data (first {display_rows} rows)")
    lines.append(df.head(display_rows).to_markdown(index=False))
    
    return "\n".join(lines)


@safe_tool
def analyze_pdf(file_path: str, max_pages: int = 50, page_range: str = "") -> str:
    """Extract and analyze text from a PDF file.
    
    Args:
        file_path: Path to the PDF file (absolute or relative to agent/user_files dir).
        max_pages: Maximum number of pages to extract (default 50).
        page_range: Optional page range like "1-5" or "1,3,5" (1-indexed).
    """
    import fitz  # PyMuPDF
    
    resolved = _resolve_file_path(file_path)
    doc = fitz.open(str(resolved))
    
    total_pages = len(doc)
    
    # Determine which pages to extract
    pages_to_extract = []
    if page_range:
        for part in page_range.split(","):
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                start = max(1, int(start.strip()))
                end = min(total_pages, int(end.strip()))
                pages_to_extract.extend(range(start - 1, end))
            else:
                page_num = int(part) - 1
                if 0 <= page_num < total_pages:
                    pages_to_extract.append(page_num)
    else:
        pages_to_extract = list(range(min(max_pages, total_pages)))
    
    # Build analysis
    lines = []
    lines.append(f"## PDF: {resolved.name}")
    lines.append(f"**Path:** {resolved}")
    lines.append(f"**Total pages:** {total_pages}")
    lines.append(f"**Pages extracted:** {len(pages_to_extract)}")
    
    # Metadata
    meta = doc.metadata
    if meta:
        meta_items = []
        for key in ["title", "author", "subject", "creator", "producer"]:
            val = meta.get(key, "")
            if val:
                meta_items.append(f"**{key.title()}:** {val}")
        if meta_items:
            lines.append("**Metadata:** " + " | ".join(meta_items))
    lines.append("")
    
    # Extract text page by page
    total_chars = 0
    total_words = 0
    for page_num in pages_to_extract:
        page = doc[page_num]
        text = page.get_text()
        total_chars += len(text)
        total_words += len(text.split())
        
        lines.append(f"### Page {page_num + 1}")
        if text.strip():
            lines.append(text.strip())
        else:
            lines.append("*(No extractable text — may be scanned/image-based)*")
        lines.append("")
    
    doc.close()
    
    # Summary at the top (insert after header)
    summary = f"**Content:** ~{total_words:,} words, ~{total_chars:,} characters across {len(pages_to_extract)} pages"
    lines.insert(5, summary)
    lines.insert(6, "")
    
    return "\n".join(lines)


@safe_tool
def analyze_image(file_path: str) -> str:
    """Analyze an image file — returns metadata, dimensions, color info, and basic statistics.
    
    Args:
        file_path: Path to the image file (absolute or relative to agent/user_files dir).
    """
    from PIL import Image
    from PIL.ExifTags import TAGS
    
    resolved = _resolve_file_path(file_path)
    img = Image.open(str(resolved))
    
    lines = []
    lines.append(f"## Image: {resolved.name}")
    lines.append(f"**Path:** {resolved}")
    lines.append(f"**Format:** {img.format or 'Unknown'}")
    lines.append(f"**Mode:** {img.mode} ({_describe_mode(img.mode)})")
    lines.append(f"**Size:** {img.width} × {img.height} pixels")
    
    file_size = resolved.stat().st_size
    if file_size > 1024 * 1024:
        lines.append(f"**File size:** {file_size / (1024*1024):.1f} MB")
    else:
        lines.append(f"**File size:** {file_size / 1024:.1f} KB")
    
    # DPI info
    dpi = img.info.get("dpi")
    if dpi:
        lines.append(f"**DPI:** {dpi[0]} × {dpi[1]}")
    
    # Animation info
    is_animated = getattr(img, "is_animated", False)
    if is_animated:
        n_frames = getattr(img, "n_frames", "?")
        lines.append(f"**Animated:** Yes ({n_frames} frames)")
    
    lines.append("")
    
    # EXIF data (for photos)
    try:
        exif_data = img._getexif()
        if exif_data:
            lines.append("### EXIF Metadata")
            interesting_tags = [
                "Make", "Model", "DateTime", "ExposureTime", "FNumber",
                "ISOSpeedRatings", "FocalLength", "LensModel", "GPSInfo",
                "ImageDescription", "Software"
            ]
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, str(tag_id))
                if tag_name in interesting_tags:
                    lines.append(f"- **{tag_name}:** {value}")
            lines.append("")
    except (AttributeError, Exception):
        pass
    
    # Color analysis
    try:
        if img.mode in ("RGB", "RGBA"):
            lines.append("### Color Analysis")
            # Get dominant colors by quantizing
            small = img.copy()
            small.thumbnail((150, 150))
            if small.mode == "RGBA":
                small = small.convert("RGB")
            quantized = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
            palette = quantized.getpalette()
            if palette:
                lines.append("**Dominant colors (top 8):**")
                for i in range(8):
                    r, g, b = palette[i*3], palette[i*3+1], palette[i*3+2]
                    hex_color = f"#{r:02x}{g:02x}{b:02x}"
                    lines.append(f"- `{hex_color}` (R:{r}, G:{g}, B:{b})")
            lines.append("")
            
            # Basic channel stats
            import numpy as np
            arr = np.array(small)
            lines.append("**Channel statistics:**")
            lines.append("| Channel | Mean | Std | Min | Max |")
            lines.append("|---------|------|-----|-----|-----|")
            for i, ch_name in enumerate(["Red", "Green", "Blue"]):
                ch = arr[:, :, i]
                lines.append(
                    f"| {ch_name} | {ch.mean():.1f} | {ch.std():.1f} | {ch.min()} | {ch.max()} |"
                )
            lines.append("")
            
            # Brightness estimate
            gray = small.convert("L")
            gray_arr = np.array(gray)
            avg_brightness = gray_arr.mean()
            brightness_pct = (avg_brightness / 255) * 100
            lines.append(f"**Average brightness:** {brightness_pct:.1f}% ({_brightness_label(brightness_pct)})")
    except Exception:
        pass
    
    img.close()
    return "\n".join(lines)


def _describe_mode(mode: str) -> str:
    """Describe a PIL image mode in human terms."""
    modes = {
        "1": "1-bit black & white",
        "L": "8-bit grayscale",
        "P": "8-bit palette",
        "RGB": "24-bit true color",
        "RGBA": "32-bit true color with alpha",
        "CMYK": "32-bit CMYK color",
        "YCbCr": "YCbCr color",
        "LAB": "L*a*b color",
        "HSV": "HSV color",
        "I": "32-bit signed integer pixels",
        "F": "32-bit floating point pixels",
    }
    return modes.get(mode, f"mode {mode}")


def _brightness_label(pct: float) -> str:
    """Describe brightness as a human-readable label."""
    if pct < 20:
        return "very dark"
    elif pct < 40:
        return "dark"
    elif pct < 60:
        return "medium"
    elif pct < 80:
        return "bright"
    else:
        return "very bright"


@safe_tool
def csv_query(file_path: str, query: str) -> str:
    """Run a pandas query or aggregation on a CSV/Excel file and return the result.
    
    Args:
        file_path: Path to the CSV/Excel file.
        query: A Python expression using the variable 'df' — e.g. 
               "df.groupby('country')['sales'].sum().sort_values(ascending=False).head(10)"
               or "df[df['age'] > 30].shape[0]" or "df.describe()"
    """
    import pandas as pd
    
    resolved = _resolve_file_path(file_path)
    suffix = resolved.suffix.lower()
    
    # Load the file
    if suffix == ".csv":
        df = pd.read_csv(resolved)
    elif suffix == ".tsv":
        df = pd.read_csv(resolved, sep="\t")
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(resolved)
    elif suffix == ".json":
        df = pd.read_json(resolved)
    elif suffix == ".parquet":
        df = pd.read_parquet(resolved)
    else:
        df = pd.read_csv(resolved)
    
    # Execute the query in a restricted namespace
    namespace = {"df": df, "pd": pd}
    try:
        result = eval(query, {"__builtins__": {}}, namespace)
    except Exception as e:
        return (
            f"Error executing query: {e}\n\n"
            f"**Columns available:** {list(df.columns)}\n"
            f"**Shape:** {df.shape}\n\n"
            f"**Query tips:**\n"
            f"- Filter: `df[df['col'] > value]`\n"
            f"- Group: `df.groupby('col')['val'].mean()`\n"
            f"- Sort: `df.sort_values('col', ascending=False)`\n"
            f"- Count: `df['col'].value_counts()`"
        )
    
    # Format the result
    lines = [f"## Query Result"]
    lines.append(f"**File:** {resolved.name}")
    lines.append(f"**Query:** `{query}`")
    lines.append("")
    
    if isinstance(result, pd.DataFrame):
        lines.append(f"**Result shape:** {result.shape[0]:,} rows × {result.shape[1]} columns")
        lines.append("")
        if len(result) > 50:
            lines.append(result.head(50).to_markdown(index=True))
            lines.append(f"\n*... showing first 50 of {len(result):,} rows*")
        else:
            lines.append(result.to_markdown(index=True))
    elif isinstance(result, pd.Series):
        lines.append(f"**Result length:** {len(result):,}")
        lines.append("")
        if len(result) > 50:
            lines.append(result.head(50).to_markdown())
            lines.append(f"\n*... showing first 50 of {len(result):,} entries*")
        else:
            lines.append(result.to_markdown())
    else:
        lines.append(f"**Result:** {result}")
    
    return "\n".join(lines)