# -*- coding: utf-8 -*-
"""通知层：把批量打分结果通过 Gmail SMTP 发送。

未配置 app_password / enabled=false 时优雅跳过（只在本地出 md）。
"""
from __future__ import annotations
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def email_ready(cfg: dict) -> bool:
    e = cfg.get("email", {})
    return bool(e.get("enabled") and e.get("app_password") and e.get("sender"))


def send_email(subject: str, body: str, attachments: list[Path] | None = None,
               cfg: dict | None = None) -> tuple[bool, str]:
    """返回 (成功?, 说明)。"""
    cfg = cfg if cfg is not None else load_config()
    e = cfg.get("email", {})
    if not email_ready(cfg):
        return False, "邮件未配置（enabled/app_password 缺失），已跳过发送"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = e["sender"]
    msg["To"] = ", ".join(e.get("recipients", [e["sender"]]))
    msg.set_content(body)

    for p in (attachments or []):
        p = Path(p)
        if not p.exists():
            continue
        if p.suffix.lower() == ".pdf":
            msg.add_attachment(p.read_bytes(), maintype="application", subtype="pdf",
                               filename=p.name)
        else:
            msg.add_attachment(p.read_bytes(), maintype="text", subtype="markdown",
                               filename=p.name)
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(e["smtp_host"], int(e.get("smtp_port", 465)), context=ctx) as s:
            s.login(e["sender"], e["app_password"])
            s.send_message(msg)
        return True, f"已发送至 {msg['To']}"
    except Exception as ex:
        return False, f"邮件发送失败: {type(ex).__name__}: {ex}"
