# OR Planer

תכנון הזמנות פרופילי אלומיניום – חילוץ מכתב יד, יצירת Excel, PDF, DXF.

## Quick Start (Streamlit Cloud)

The app runs at: **https://or-planer.streamlit.app** (or your custom URL)

No install needed — open the link on any phone, tablet, or computer.

## Local Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get free API key:** https://aistudio.google.com/

3. **Create `.env` file:**
   ```bash
   copy .env.example .env
   ```
   Add your `GOOGLE_API_KEY`.

4. **Run:**
   ```bash
   streamlit run app.py
   ```

## Deploy to Streamlit Cloud

1. Push this repo to GitHub
2. Go to https://share.streamlit.io
3. Connect the repo, select `app.py`
4. Add API keys in **Settings → Secrets**:
   ```toml
   GOOGLE_API_KEY = "your-key"
   ANTHROPIC_API_KEY = "your-key"
   OPENROUTER_API_KEY = "your-key"
   ```
5. Done — you get a public URL that works on mobile

## Perfect results checklist (Hebrew)

See **[PERFECT_INPUT_CHECKLIST.md](PERFECT_INPUT_CHECKLIST.md)** or **`PERFECT_INPUT_CHECKLIST.txt`** (same folder, plain text, UTF-8) — every field to fill for consistent Excel/PDF/DXF output.  
Full walkthrough: **[USER_GUIDE.md](USER_GUIDE.md)** (Hebrew).

## Usage

1. Open the app (browser or mobile)
2. Upload handwritten sketch images (JPG/PNG) or a JSON file
3. Edit/fix any missing data in the editor
4. Click "צור הזמנה" to generate files
5. Download Excel, PDF, DXF

## Output Files

In `output/{project_id}/`:
- `______{id}-הזמנה.xlsx` – Order spreadsheet
- `______{id}-הזמנה.pdf` – Order summary PDF
- `______{id}-חבילה.pdf` – Single PDF: summary + every panel sheet (requires `pypdf` from `requirements.txt`)
- `dwg/` – DXF files per panel (for CNC)
- `pdf_panels/` – PDF drawing per panel
- `DWG-{id}.zip` – All DXF files zipped
- `PDF-{id}.zip` – All panel PDFs zipped

## API Fallback Chain

1. **Gemini** (free, 20/day) — primary
2. **Claude** (~$0.001/image) — if Gemini quota exceeded
3. **OpenRouter** (free) — last resort
4. **JSON upload** — no API needed at all
