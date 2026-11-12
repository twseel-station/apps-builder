#!/usr/bin/env python3
"""One merged Telegram message per pipeline run, written in Saudi dialect.

Called from the `notify` composite action, so every repo (apps-builder,
backend, ...) shares the same voice and the same single function.

Env inputs
    TG_BOT / TG_CHAT   Telegram credentials (silently skipped when empty)
    KIND               app | deploy | check          -> which phrase pool to use
    STATUS             success | failure | cancelled
    TITLE              e.g. "client-app" or "backend"
    ENV                test | production | staging ...
    STAGE              where it broke (failure only)
    DETAILS            "key: value" lines, one per line
    LINKS              "label|url" lines, one per line
"""

import datetime
import html
import os
import random
import urllib.parse
import urllib.request
import uuid
import zoneinfo

ENV_LABEL = {
    "test": "التست 🧪",
    "staging": "التست 🧪",
    "production": "اللايف 🔴",
    "prod": "اللايف 🔴",
}

# {t} = title, {e} = environment, {s} = failing stage
POOLS = {
    "app": {
        "success": [
            "✅ أبشر! <b>{t}</b> جاهز على {e}",
            "🚀 تمّ يا طويل العمر، <b>{t}</b> نزل على {e}",
            "🔥 ما قصّرنا، <b>{t}</b> خلص وانرفع على {e}",
            "😎 <b>{t}</b> جاهز على {e}.. تفضّل جرّب",
            "🫡 الله يعطيك العافية، <b>{t}</b> انبنى على {e} بسلام",
        ],
        "failure": [
            "❌ يا ساتر! <b>{t}</b> طاح عند {s}",
            "🚨 فيه مشكلة في <b>{t}</b>، وقف عند {s}",
            "😵 <b>{t}</b> ما كمّل، العلّة في {s}",
            "⛔ ما مشت معنا، <b>{t}</b> فشل عند {s}",
            "🧯 الحقوا! <b>{t}</b> تعطّل في {s}",
        ],
        "cancelled": [
            "⏹️ <b>{t}</b> انلغى قبل لا يخلص",
            "🛑 أحد وقّف <b>{t}</b> في النص",
        ],
    },
    "deploy": {
        "success": [
            "✅ تم الرفع! <b>{t}</b> شغّال على {e}",
            "🚀 أبشر، <b>{t}</b> نزل على سيرفر {e}",
            "🔥 <b>{t}</b> انرفع على {e} والداتابيز ما انلمست",
            "🫡 خلصنا، <b>{t}</b> على {e} حدّثناه بدون ما نوقف الخدمة",
        ],
        "failure": [
            "❌ الرفع فشل! <b>{t}</b> على {e} طاح عند {s}",
            "🚨 يا ساتر، رفع <b>{t}</b> على {e} وقف عند {s}",
            "😵 <b>{t}</b> ما نزل على {e}، المشكلة في {s}",
        ],
        "cancelled": ["⏹️ رفع <b>{t}</b> على {e} انلغى"],
    },
    "check": {
        "success": ["✅ فحص <b>{t}</b> سليم"],
        "failure": [
            "❌ فحص <b>{t}</b> ما عدّى، العلّة في {s}",
            "🚨 <b>{t}</b> فيه خطأ في الكود عند {s}",
        ],
        "cancelled": ["⏹️ فحص <b>{t}</b> انلغى"],
    },
}


def lines(name):
    return [ln.strip() for ln in os.environ.get(name, "").splitlines() if ln.strip()]


def build_message():
    kind = os.environ.get("KIND", "app")
    status = os.environ.get("STATUS", "success")
    seed = os.environ.get("GITHUB_RUN_ID", "0") + os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    rng = random.Random(seed)  # same run => same wording, new run => new mood

    env_key = os.environ.get("ENV", "").lower()
    env_text = ENV_LABEL.get(env_key, env_key or "—")
    pool = POOLS.get(kind, POOLS["app"]).get(status) or POOLS["app"]["failure"]
    head = rng.choice(pool).format(
        t=html.escape(os.environ.get("TITLE", "pipeline")),
        e=html.escape(env_text),
        s=html.escape(os.environ.get("STAGE") or "خطوة غير معروفة"),
    )

    out = [head]

    # Duration taken by the action/run
    duration = os.environ.get("DURATION", "").strip()
    if duration:
        out.append(f"⏱️ مدة الأكشن: <code>{html.escape(duration)}</code>")

    for ln in lines("DETAILS"):
        key, _, val = ln.partition(":")
        out.append(f"• {html.escape(key.strip())}: <code>{html.escape(val.strip())}</code>")

    # Test account reminder in test/dev environment
    test_account = os.environ.get("TEST_ACCOUNT", "").strip()
    if test_account and env_key in ("test", "staging", "dev"):
        out.append(f"🔑 حساب التجربة: <code>{html.escape(test_account)}</code>")

    links = []
    for ln in lines("LINKS"):
        label, _, url = ln.partition("|")
        if url.strip():
            links.append(f'<a href="{html.escape(url.strip(), quote=True)}">{html.escape(label.strip())}</a>')
    if links:
        out.append("🔗 " + " · ".join(links))
    return "\n".join(out)


def send_document(bot, chat, file_path, caption=""):
    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = bytearray()

    def add_field(name, value):
        body.extend(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode("utf-8")
        )

    add_field("chat_id", chat)
    if caption:
        cap = caption if len(caption) <= 1024 else caption[:1020] + "..."
        add_field("caption", cap)
        add_field("parse_mode", "HTML")

    mime_type = "application/vnd.android.package-archive" if filename.endswith(".apk") else "application/zip"
    body.extend(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: {mime_type}\r\n\r\n".encode(
            "utf-8"
        )
    )
    body.extend(file_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot}/sendDocument",
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "AntigravityTelegramBot/1.0",
        },
    )
    req.add_header("Content-Length", str(len(body)))
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read()


def main():
    bot, chat = os.environ.get("TG_BOT", ""), os.environ.get("TG_CHAT", "")
    text = build_message()
    print(text)
    if not (bot and chat):
        print("Telegram credentials not set, skipping send.")
        return

    doc_path = os.environ.get("DOCUMENT", "").strip()
    sent_doc = False
    if doc_path and os.path.isfile(doc_path):
        size = os.path.getsize(doc_path)
        print(f"Sending document to Telegram: {doc_path} ({size} bytes)")
        try:
            send_document(bot, chat, doc_path, caption=text)
            sent_doc = True
            print("Telegram document sent successfully.")
        except Exception as exc:
            print(f"::warning::Telegram sendDocument failed: {exc}, falling back to sendMessage")

    if not sent_doc:
        data = urllib.parse.urlencode(
            {
                "chat_id": chat,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
        ).encode()
        try:
            urllib.request.urlopen(
                f"https://api.telegram.org/bot{bot}/sendMessage", data=data, timeout=15
            ).read()
            print("Telegram message sent successfully.")
        except Exception as exc:  # a notification must never fail the pipeline
            print(f"::warning::Telegram send failed: {exc}")


if __name__ == "__main__":
    main()
