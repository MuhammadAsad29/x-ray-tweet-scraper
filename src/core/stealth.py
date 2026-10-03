from typing import List, Dict, Any


def get_stealth_browser_args() -> List[str]:
    """Returns chromium command-line flags to avoid automation detection."""
    return [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-infobars",
        "--window-position=0,0",
        "--ignore-certificate-errors",
        "--ignore-certificate-errors-spki-list",
    ]


def get_default_context_options(user_agent: str) -> Dict[str, Any]:
    """Returns Playwright browser context options mimicking a real desktop browser."""
    return {
        "user_agent": user_agent,
        "viewport": {"width": 1920, "height": 1080},
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "color_scheme": "dark",
        "extra_http_headers": {
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


STEALTH_INIT_SCRIPT = """
// Mask navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Ensure window.chrome exists
if (!window.chrome) {
    window.chrome = {
        runtime: {}
    };
}
"""
