"""Dữ liệu hoạt động mô phỏng (chiến dịch + hội thoại) để các màn hình DN không trống khi mới cài.
Chỉ chạy khi chưa có chiến dịch/tin nhắn nào và dữ liệu mẫu CORPxxxx còn tồn tại. Bị xóa cùng 'Xóa dữ liệu mẫu'."""
import random
from datetime import datetime, timedelta

from src.database import SessionLocal
from src.accounts.service import AuthUser
from .models import CorpCustomer, CorpCampaign, CorpCampaignTarget, CorpMessage, CorpSetting, CorpOpportunity
from .outreach import build_audience, make_drafts, AudienceIn, DraftsIn
from .conversations import classify

REPLIES = {
    "vi": {"interested": ["Anh quan tâm, em gửi giúp anh bản đề xuất nhé", "Cho bên anh xin báo giá chi tiết"], "meeting": ["Mai 15h em qua văn phòng bên anh trao đổi nhé"],
           "rate": ["Lãi suất bên em đang cao hơn bên anh đang dùng"], "competitor": ["Bên anh đang dùng ngân hàng khác rồi em"],
           "noneed": ["Hiện tại chưa có nhu cầu em nhé"], "approval": ["Anh cần xin ý kiến công ty mẹ đã"], "docs": ["Cần chuẩn bị hồ sơ gì em nhỉ?"], "ack": ["Ok cảm ơn em"]},
    "zh": {"interested": ["我们有兴趣，请发一下方案资料"], "meeting": ["可以，明天下午约个电话沟通"], "rate": ["你们的利率比现在的银行高"], "noneed": ["暂时不需要，谢谢"], "approval": ["需要先请示总公司"], "ack": ["好的，谢谢"]},
    "en": {"interested": ["Interested, please send the proposal"], "noneed": ["Not now, thanks"], "rate": ["The rate seems higher than our current bank"], "ack": ["Noted, thanks"]},
}


def ensure_demo_activity():
    db = SessionLocal()
    try:
        if db.query(CorpCampaign).count() or db.query(CorpMessage).count() or db.query(CorpSetting).filter_by(key="_demo_cleared").first():
            return False
        if not db.query(CorpCustomer).filter(CorpCustomer.customer_id.op("GLOB")("CORP[0-9][0-9][0-9][0-9]")).count():
            return False
        rng = random.Random(7)
        admin = AuthUser(0, "demo", "Hệ thống (mẫu)", "admin", "Hệ thống (mẫu)")
        now = datetime.utcnow()
        for name, product, channel, fw, n, days0 in [("UPAS cho FDI nhập khẩu lớn", "UPAS", "zalo", "consultative", 16, 30),
                                                     ("Gia hạn hạn mức vay vốn lưu động", "VAY_VLD", "email", "spin", 12, 45)]:
            aud = build_audience(db, admin, AudienceIn(product=product, channel=channel, min_score=60, limit=60))
            chosen = aud["eligible"][:n]
            if not chosen:
                continue
            cp = CorpCampaign(name=name, product=product, channel=channel, language="auto", framework=fw, filters={"min_score": 60},
                              owner="demo", owner_rm="Hệ thống (mẫu)", created_at=now - timedelta(days=days0))
            db.add(cp); db.flush()
            ds = {d["customer_id"]: d for d in make_drafts(db, admin, DraftsIn(product=product, channel=channel, language="auto", framework=fw,
                                                                              customer_ids=[s["customer_id"] for s in chosen]))}
            for i, s in enumerate(chosen):
                d = ds[s["customer_id"]]
                t = CorpCampaignTarget(campaign_id=cp.id, customer_id=s["customer_id"], language=d["language"], subject=d["subject"], body=d["body"])
                db.add(t)
                if i >= int(n * 0.8):
                    continue                                   # ~20% chưa liên hệ
                sent = now - timedelta(days=rng.randint(15, days0), hours=rng.randint(0, 8))   # > giãn cách liên hệ mặc định (14 ngày) để tệp vẫn còn khách đủ điều kiện
                t.status, t.sent_at, t.updated_at = "Đã liên hệ", sent, sent
                db.add(CorpMessage(customer_id=s["customer_id"], campaign_id=cp.id, direction="out", channel=channel, language=d["language"],
                                   subject=d["subject"], body=d["body"], product=product, created_by="demo", created_at=sent))
                if rng.random() < 0.55:
                    lang = d["language"]
                    pool = REPLIES.get(lang) or REPLIES["vi"]
                    intent = rng.choices(list(pool), [4, 2, 2, 1, 2, 1, 1, 1][: len(pool)] or None)[0]
                    txt = rng.choice(pool[intent])
                    rt = sent + timedelta(hours=rng.randint(2, 70))
                    if rt < now:
                        db.add(CorpMessage(customer_id=s["customer_id"], campaign_id=cp.id, direction="in", channel=channel, language=lang, body=txt,
                                           intent=classify(txt), product=product, created_by="demo", created_at=rt))
                        ci = classify(txt)
                        t.status = "Từ chối" if ci in ("noneed", "optout") else "Quan tâm" if ci in ("interested", "meeting", "docs") else "Phản hồi"
                        t.updated_at = rt
                        if ci in ("interested", "meeting") and rng.random() < 0.35:
                            t.status = "Chuyển đổi"
        db.commit()
        return True
    finally:
        db.close()


if __name__ == "__main__":
    print("demo activity seeded" if ensure_demo_activity() else "skipped")
