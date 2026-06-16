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
    "run_local_validator": "running local deterministic validation is read-only",
    "export_run_summary": "exporting from local canonical artifacts is read-only",
}

YELLOW_ACTIONS = {
    "open_logged_in_page": "logged-in pages may expose private data",
    "use_real_chrome_profile": "real browser profiles may expose signed-in state",
    "accept_cookie_banner": "cookie acceptance can change site state",
    "change_region": "region changes can affect account or quote context",
    "change_language": "language changes can affect page content and account state",
    "change_currency": "currency changes can affect quote context",
    "change_store": "store selection can affect quote context",
    "select_product_spec": "spec selection changes page quote context",
    "open_coupon_details": "coupon details are allowed only when no claiming occurs",
    "open_account_menu": "account-adjacent menus may expose private data",
    "use_browser_history": "browser history may expose unrelated private context",
    "save_sensitive_screenshot": "screenshots can capture personal data",
}

RED_ACTIONS = {
    "click_claim_coupon": "coupon claiming mutates account state",
    "add_to_cart": "cart actions mutate account or session state",
    "submit_login": "password or login submission is prohibited",
    "post_comment": "posting comments mutates public or account state",
    "purchase_item": "purchase/payment actions are prohibited",
    "send_message": "messaging mutates account state",
    "send_email": "email actions mutate account state",
    "submit_captcha": "CAPTCHA or identity verification handling is prohibited",
    "submit_identity_verification": "identity verification handling is prohibited",
    "change_account_setting": "account/security/payment settings are prohibited",
    "change_payment_setting": "payment settings are prohibited",
    "change_address": "address mutation is prohibited",
    "change_privacy_setting": "privacy settings mutation is prohibited",
    "scan_tabs": "scanning unrelated tabs is prohibited",
    "read_private_messages": "unrelated private messages are out of scope",
    "read_order_history": "unrelated private order history is out of scope",
    "export_browser_profile": "browser profile export is prohibited",
    "export_cookies": "cookie export is prohibited",
    "export_tokens": "token export is prohibited",
    "export_local_storage": "local storage export is prohibited",
    "export_session_storage": "session storage export is prohibited",
    "export_har": "HAR/network log export is prohibited by default",
    "use_proxy": "proxy or stealth browsing is out of scope",
    "use_stealth": "stealth browsing is out of scope",
    "bypass_antibot": "anti-bot bypass is prohibited",
    "follow_account": "following mutates account state",
    "like_post": "liking mutates account or public state",
    "repost": "reposting mutates account or public state",
}


def classify_action(action: str) -> ActionDecision:
    if action in GREEN_ACTIONS:
        return ActionDecision(action, "green", True, GREEN_ACTIONS[action])
    if action in YELLOW_ACTIONS:
        return ActionDecision(action, "yellow", False, YELLOW_ACTIONS[action])
    if action in RED_ACTIONS:
        return ActionDecision(action, "red", False, RED_ACTIONS[action])
    return ActionDecision(action, "unknown", False, "unknown browser action requires user review")
