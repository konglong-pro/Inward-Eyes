from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionDecision:
    action: str
    classification: str
    allowed: bool
    reason: str


GREEN_ACTIONS = {
    "open_url": "opening a task-scoped URL is read-only",
    "scroll_page": "scrolling observes visible content only",
    "expand_details": "expanding details is read-only when it does not mutate account state",
    "read_visible_text": "reading visible text is read-only",
    "save_artifacts": "saving local artifacts is part of the workflow",
    "copy_current_url": "copying current URL is read-only",
    "capture_current_visible_page": "capturing one approved visible page is read-only",
}

YELLOW_ACTIONS = {
    "open_logged_in_page": "logged-in pages may expose private data",
    "use_real_chrome_profile": "real browser profiles may expose signed-in state",
    "accept_cookie_banner": "cookie acceptance can change site state",
    "change_region": "region changes can affect account or quote context",
    "select_product_spec": "spec selection changes page quote context",
    "open_coupon_details": "coupon details are allowed only when no claiming occurs",
    "save_sensitive_screenshot": "screenshots can capture personal data",
}

RED_ACTIONS = {
    "click_claim_coupon": "coupon claiming mutates account state",
    "add_to_cart": "cart actions mutate account or session state",
    "submit_login": "password or login submission is prohibited",
    "post_comment": "posting comments mutates public or account state",
    "purchase_item": "purchase/payment actions are prohibited",
    "send_message": "messaging mutates account state",
    "submit_captcha": "CAPTCHA or identity verification handling is prohibited",
    "change_account_setting": "account/security/payment settings are prohibited",
}


def classify_action(action: str) -> ActionDecision:
    if action in GREEN_ACTIONS:
        return ActionDecision(action, "green", True, GREEN_ACTIONS[action])
    if action in YELLOW_ACTIONS:
        return ActionDecision(action, "yellow", False, YELLOW_ACTIONS[action])
    if action in RED_ACTIONS:
        return ActionDecision(action, "red", False, RED_ACTIONS[action])
    return ActionDecision(action, "unknown", False, "unknown browser action requires user review")
