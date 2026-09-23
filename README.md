---
title: TrackerForShopping
emoji: ⚡
colorFrom: indigo
colorTo: emerald
sdk: docker
app_port: 7860
pinned: false
---

# ⚡ Smart Price & Deal Tracker Studio

A real-time price deal intelligence tracker and notifier with automated background polling, discrete GPU telemetry, and Telegram alerts.

### Supported Catalogs
- **Lenovo Outlet India**: Refurbished laptops, GPU & VRAM extraction, 1-minute automated polling with deduplicated discount alerts.
- **IKEA India**: Modular sofas & living room catalog with IKEA Family instant deal discounts.
- **Amazon & Flipkart**: Custom product tracking with target price notifications.

### Environment Configuration (HF Space Secrets)
Configure these secrets in **Settings -> Variables and Secrets**:
- `TELEGRAM_BOT_TOKEN`: Your Telegram Bot API token (optional)
- `TELEGRAM_CHAT_ID`: Your Telegram Chat ID for alerts (optional)
- `RESIDENTIAL_PROXY_URL`: Rotating proxy URL if desired (optional)
