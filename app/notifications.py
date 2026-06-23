#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通知服务：微信推送 + 邮件发送"""

import json
import urllib.request
from datetime import datetime

from database import get_setting


def send_wechat(message: str) -> bool:
    """通过 OpenClaw 发微信通知"""
    target = get_setting("wechat_target", "")
    account_id = get_setting("wechat_account", "")
    if not target:
        return False
    try:
        gateway = get_setting("openclaw_gateway", "http://127.0.0.1:33970")
        payload = {
            "channel": "openclaw-weixin",
            "to": target,
            "message": message,
        }
        if account_id:
            payload["accountId"] = account_id
        req = urllib.request.Request(
            f"{gateway}/api/message/send",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        print(f"微信提醒失败: {e}")
        return False


def send_email(subject: str, body_html: str) -> bool:
    """通过 SMTP 发送 HTML 邮件"""
    server = get_setting("smtp_server", "")
    port = get_setting("smtp_port", "465")
    from_addr = get_setting("smtp_from", "")
    auth_code = get_setting("smtp_auth_code", "")
    to_addr = get_setting("smtp_to", "")

    if not server or not from_addr or not auth_code or not to_addr:
        print("邮件配置不完整，跳过")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body_html, "html", "utf-8")
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject

        if port == "465":
            with smtplib.SMTP_SSL(server, int(port), timeout=10) as smtp:
                smtp.login(from_addr, auth_code)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, int(port), timeout=10) as smtp:
                smtp.starttls()
                smtp.login(from_addr, auth_code)
                smtp.send_message(msg)
        print(f"✅ 邮件发送成功: {subject}")
        return True
    except Exception as e:
        print(f"邮件发送异常: {e}")
        return False


def build_low_stock_message(rows) -> str:
    """构造低库存微信消息"""
    lines = [f"🏠 家庭耗材库存提醒（{datetime.now().strftime('%m-%d %H:%M')}）", ""]
    lines.append(f"⚠️ {len(rows)} 件耗材库存不足：\n")
    for r in rows:
        marker = "🔴" if r["stock"] <= 0 else "🟡"
        lines.append(f"{marker} {r['icon']} {r['name']}: {r['stock']}/{r['min_stock']}{r['unit']}")
    return "\n".join(lines)


def build_low_stock_email(rows) -> tuple:
    """构造低库存邮件，返回 (subject, body_html)"""
    mail_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    mail_date_short = datetime.now().strftime("%y%m%d")

    detail_lines = []
    for r in rows:
        marker = "🔴" if r["stock"] <= 0 else "🟡"
        detail_lines.append(f"{marker} {r['icon']} {r['cat_name']} | {r['name']}: {r['stock']}/{r['min_stock']}{r['unit']}")
    detail_str = "\n".join(detail_lines)

    subject = f"【Home Stash】耗材低库存提醒 | {mail_date_short}"
    body_html = f"""<pre style="font-family: Monaco, Consolas, monospace; font-size: 13px; line-height: 1.6;">
⚠️ 家庭耗材库存提醒
📊 有 {len(rows)} 件耗材库存不足
🕐 {mail_date}
=============================================================

📋 低库存清单
=============================================================
{detail_str}

=============================================================
👉 打开 Home Stash 管理库存
</pre>"""
    return subject, body_html
