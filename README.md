# Australian Fuel Import Monitor

Tracks oil and liquid fuel tankers en route to Australia. Updated nightly from AIS vessel tracking data and Australian Government petroleum statistics.

## Setup

### Prerequisites
- Node.js 20+
- Python 3.12+

### Install
```bash
npm install
pip install -r pipeline/requirements.txt
```

### Run locally
```bash
npm run dev
```

### Run data pipeline
```bash
export AISSTREAM_API_KEY=your_key_here
python -m pipeline.orchestrator
```

## Deployment

Deployed automatically via GitHub Actions to GitHub Pages. Runs nightly at 02:00 AEST.

### Required secrets
- `AISSTREAM_API_KEY` — Get a free key at [aisstream.io](https://aisstream.io)

### Custom domain
1. Add your domain in GitHub repo Settings → Pages → Custom domain
2. Create a CNAME DNS record pointing to `<username>.github.io`
3. GitHub provides free HTTPS via Let's Encrypt
