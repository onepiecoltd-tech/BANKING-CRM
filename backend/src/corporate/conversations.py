"""Hội thoại với khách hàng DN: ghi nhận tin đi/đến, phân loại ý định (vi/en/zh), gợi ý trả lời, nhắc theo dõi."""
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from pydantic import BaseModel

from src.database import SessionLocal
from src.accounts.deps import current_user, client_ip
from src.accounts.service import audit
from .models import (CorpCustomer, CorpMessage, CorpOpportunity, CorpOptOut, CorpCampaignTarget, CorpInteraction)
from .catalog import PRODUCTS, TITLES, STAGE_PROB
from .access import get_settings, rm_filter, get_customer_or_403
from . import agent, scoring
from .router import _get_one

router = APIRouter(prefix="/api/corp", tags=["corporate-conversations"])


# ── phân loại ý định ─────────────────────────────────────────────────────────
def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


INTENT_RULES = [  # thứ tự = độ ưu tiên
    ("optout", ["dung nhan", "dung nhan tin", "khong nhan tin", "ngung gui", "xoa so", "dung lien he", "khong lien he nua", "unsubscribe",
                "stop messaging", "do not contact", "don't contact", "remove me", "别发", "不要再发", "不用再联系", "请勿打扰", "退订"]),
    ("meeting", ["hen gap", "gap truc tiep", "den van phong", "sap xep lich", "dat lich", "goi lai", "lien he lai", "meeting", "call me", "call back",
                 "schedule a call", "let's meet", "约", "见面", "电话沟通", "回电话", "面谈"]),
    ("interested", ["quan tam", "gui thong tin", "gui bao gia", "gui de xuat", "tu van them", "muon tim hieu", "interested", "send details",
                    "send me", "more information", "proposal", "感兴趣", "发资料", "报价", "发方案", "了解一下"]),
    ("docs", ["ho so", "chung tu", "thu tuc", "can giay to", "can chuan bi gi", "documents required", "what documents", "资料", "需要什么文件", "需要哪些材料", "手续"]),
    ("approval", ["xin y kien", "bao cao tong cong ty", "cong ty me", "hoi dong", "ban giam doc", "head office", "need approval", "headquarters",
                  "总公司", "请示", "老板", "董事会", "集团批准"]),
    ("rate", ["lai suat", "lai cao", "phi cao", "muc phi", "bieu phi", "gia dat", "qua dat", "dat hon", "rat dat", "cao hon", "re hon", "giam phi", "uu dai hon", "rate is high", "too expensive", "fee is high",
              "lower rate", "better rate", "太贵", "利率高", "费用高", "优惠", "利率能不能", "便宜"]),
    ("competitor", ["dang dung ngan hang", "da co ngan hang", "dang hop tac voi ngan hang", "vietcombank", "vcb", "bidv", "vietinbank", "techcombank",
                    "mbbank", "acb", "vpbank", "hdbank", "already with", "already have a bank", "our bank", "我们有合作银行", "已有银行", "已经有合作", "现有银行"]),
    ("noneed", ["chua co nhu cau", "chua can", "khong can", "khong co nhu cau", "chua phai luc", "no need", "not now", "not interested",
                "don't need", "暂时不需要", "不需要", "没有需求", "目前不用"]),
    ("ack", ["cam on", "da nhan", "ok", "thanks", "thank you", "noted", "谢谢", "好的", "收到"]),
]

INTENT_LABEL = {
    "optout": "Từ chối nhận tin", "meeting": "Hẹn gặp / gọi lại", "interested": "Quan tâm", "docs": "Hỏi hồ sơ / thủ tục",
    "approval": "Cần xin ý kiến cấp trên", "rate": "Lo ngại giá / phí", "competitor": "Đang dùng ngân hàng khác",
    "noneed": "Chưa có nhu cầu", "ack": "Xác nhận / cảm ơn", "other": "Khác",
}
HOT = {"meeting", "interested", "docs"}
OBJECTION = {"rate", "competitor", "noneed"}


def classify(text: str) -> str:
    f = " " + _fold(text) + " "
    raw = text.lower()
    for intent, kws in INTENT_RULES:
        for k in kws:
            if re.search(r"[\u4e00-\u9fff]", k):
                if k in raw:
                    return intent
            elif len(k) <= 3:
                if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", f):
                    return intent
            elif k in f:
                return intent
    return "other"


def detect_lang(text: str, default: str = "vi") -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", text.lower()):
        return "vi"
    if re.search(r"\b(the|and|please|we|our|is|are|thanks|rate|need)\b", text.lower()):
        return "en"
    return default


# ── mẫu trả lời gợi ý (không hứa lãi suất / hạn mức / phê duyệt) ─────────────
REPLIES = {
    "interested": {
        "vi": "Dạ em cảm ơn Anh/Chị đã quan tâm ạ. Em xin phép gửi tóm tắt giải pháp {product} phù hợp với {company} qua kênh này trong hôm nay, và đề xuất một buổi trao đổi ngắn 15 phút để làm rõ nhu cầu thực tế. Anh/Chị tiện khung giờ nào trong tuần này ạ?",
        "zh": "感谢您的关注！我今天会通过本渠道发送适合{company}的{product}方案摘要，并建议安排15分钟的简短沟通以了解实际需求。请问您本周哪个时段方便？",
        "en": "Thank you for your interest. I will send a short summary of our {product} solution for {company} today and suggest a 15-minute call to understand your actual needs. Which slot works for you this week?"},
    "meeting": {
        "vi": "Dạ vâng ạ, em xin xác nhận lịch trao đổi. Em đề xuất {slot_vi}; nếu thời gian này chưa thuận tiện, Anh/Chị cho em xin khung giờ khác ạ. Em sẽ chuẩn bị trước thông tin về {product} theo tình hình của {company}.",
        "zh": "好的，我来确认沟通安排。建议{slot_zh}；如不方便，请告知其他时间。我会根据{company}的情况提前准备{product}的相关资料。",
        "en": "Certainly — let me confirm a time. I suggest {slot_en}; if that is inconvenient, please propose another slot. I will prepare {product} materials based on {company}'s situation beforehand."},
    "docs": {
        "vi": "Dạ để triển khai {product}, thông thường ngân hàng cần hồ sơ pháp lý, báo cáo tài chính gần nhất và các chứng từ liên quan đến nhu cầu cụ thể. Em sẽ gửi danh mục hồ sơ chi tiết theo đúng trường hợp của {company}; danh mục cuối cùng phụ thuộc quy định hiện hành của ngân hàng ạ.",
        "zh": "办理{product}通常需要法律文件、最近期财务报表以及与具体业务相关的单据。我会按{company}的具体情况发送详细清单；最终清单以银行现行规定为准。",
        "en": "For {product}, the bank typically needs legal documents, the latest financial statements and documents related to the specific transaction. I will send a checklist tailored to {company}; the final list depends on the bank's prevailing requirements."},
    "approval": {
        "vi": "Dạ em hiểu, quyết định cần được thông qua cấp quản lý/công ty mẹ ạ. Để Anh/Chị thuận tiện báo cáo, em sẽ gửi bản tóm tắt ngắn gọn về {product} (lợi ích, quy trình, hồ sơ). Nếu cần, em sẵn sàng tham gia một buổi giải thích cùng đại diện của công ty.",
        "zh": "明白，该决定需要管理层/总公司批准。为方便您汇报，我会提供一份关于{product}的简要说明（优势、流程、材料）。如有需要，我也乐意与贵司代表一起沟通说明。",
        "en": "Understood — the decision needs sign-off from management / head office. To help your reporting, I will send a concise summary of {product} (benefits, process, documents) and I am happy to join a briefing with your colleagues if useful."},
    "rate": {
        "vi": "Dạ em hiểu mối quan tâm về chi phí ạ. Chi phí thực tế phụ thuộc cấu trúc giao dịch, thời hạn và hồ sơ của {company}, nên em xin phép trao đổi số liệu cụ thể để đề xuất phương án tối ưu rồi báo cáo bên em xem xét. Anh/Chị có thể chia sẻ mức chi phí hiện tại để em so sánh trên cùng điều kiện được không ạ?",
        "zh": "理解您对成本的关注。实际成本取决于{company}的交易结构、期限及材料，我想先了解具体数据，再提出最优方案并提交内部评估。您方便分享目前的成本水平，以便在同等条件下比较吗？",
        "en": "I understand the cost concern. Actual cost depends on {company}'s transaction structure, tenor and documentation, so I would like to review the specifics and propose the best option for internal assessment. Could you share your current cost level so we can compare on like-for-like terms?"},
    "competitor": {
        "vi": "Dạ em hiểu {company} đã có ngân hàng đối tác ạ. Nhiều doanh nghiệp vẫn chọn phân bổ một phần nhu cầu sang ngân hàng thứ hai để dự phòng hạn mức và linh hoạt dịch vụ. Em xin phép giới thiệu ngắn gọn {product} để Anh/Chị có thêm lựa chọn khi cần, không ảnh hưởng quan hệ hiện tại ạ.",
        "zh": "明白{company}已有合作银行。许多企业会将部分业务分配给第二家银行，以备额度与服务灵活性之需。我想简要介绍{product}，作为您需要时的额外选择，不影响现有合作关系。",
        "en": "I understand {company} already works with another bank. Many companies allocate part of their needs to a second bank for limit back-up and service flexibility. May I briefly introduce {product} as an additional option, without affecting your existing relationship?"},
    "noneed": {
        "vi": "Dạ em cảm ơn Anh/Chị đã phản hồi ạ. Em xin phép lưu lại thông tin và sẽ chỉ liên hệ lại khi có thay đổi phù hợp với kế hoạch của {company} (ví dụ khi mở rộng sản xuất hoặc tăng kim ngạch XNK). Khi cần hỗ trợ, Anh/Chị cứ liên hệ trực tiếp em nhé.",
        "zh": "感谢您的回复。我会记录相关信息，仅在出现与{company}计划相符的变化（例如扩产或进出口增长）时再联系您。如有需要，欢迎随时联系我。",
        "en": "Thank you for letting me know. I will note this and only reach out again if something relevant to {company}'s plans changes (e.g. expansion or higher trade volumes). Please contact me directly whenever you need support."},
    "optout": {
        "vi": "Dạ em xin lỗi vì đã làm phiền và xin ghi nhận yêu cầu: bên em sẽ không gửi thêm thông tin tiếp thị qua kênh này. Nếu Anh/Chị cần hỗ trợ nghiệp vụ, vẫn có thể liên hệ trực tiếp em ạ. Em cảm ơn.",
        "zh": "抱歉打扰，已记录您的要求：我们将不再通过此渠道发送营销信息。如需业务支持，仍可直接联系我。谢谢。",
        "en": "Apologies for the disturbance — your request is noted and we will not send further marketing messages on this channel. You are welcome to contact me directly for any service needs. Thank you."},
    "ack": {
        "vi": "Dạ em cảm ơn Anh/Chị ạ. Em sẽ theo dõi và chủ động cập nhật khi có thông tin mới liên quan đến {product} cho {company}.",
        "zh": "谢谢！有关{company}的{product}如有新进展，我会及时跟进并告知。",
        "en": "Thank you. I will follow up and update you proactively on {product} for {company}."},
    "other": {
        "vi": "Dạ em cảm ơn Anh/Chị đã phản hồi ạ. Để hỗ trợ đúng nhu cầu của {company}, Anh/Chị cho em xin thêm một chút thông tin hoặc một khung giờ ngắn để trao đổi trực tiếp được không ạ?",
        "zh": "感谢您的回复。为了更好地满足{company}的需求，能否请您补充一些信息，或约一个简短的沟通时间？",
        "en": "Thank you for your reply. To support {company}'s needs properly, could you share a bit more detail or a short slot to talk?"},
}
FOLLOWUP = {  # theo nhịp 3 / 7 / 14 ngày
    3: {"vi": "Dạ em xin phép nhắc lại thông tin em đã gửi về {product} cho {company}. Nếu Anh/Chị cần em làm rõ điểm nào hoặc trình bày nhanh trong 10 phút, em sẵn sàng ạ.",
        "zh": "跟进一下之前发送的{company}{product}相关信息。如有需要澄清的地方，或希望我用10分钟简要介绍，随时告知。",
        "en": "A quick follow-up on the {product} information I sent for {company}. If any point needs clarifying, I'm glad to walk you through it in 10 minutes."},
    7: {"vi": "Dạ em xin chia sẻ thêm một thông tin hữu ích cho {company}: các doanh nghiệp cùng ngành thường xem xét {product} khi kế hoạch sản xuất/xuất nhập khẩu có thay đổi. Nếu phù hợp, em gửi bản tóm tắt ngắn để Anh/Chị tham khảo ạ.",
        "zh": "再分享一点对{company}可能有用的信息：同行业企业在生产/进出口计划变化时通常会考虑{product}。如合适，我发送一份简要说明供参考。",
        "en": "One more point that may help {company}: companies in your industry often look at {product} when production or trade plans change. If useful, I can send a short summary."},
    14: {"vi": "Dạ đây là lần liên hệ cuối của em về {product} để tránh làm phiền {company}. Nếu sau này có nhu cầu, Anh/Chị cứ nhắn em bất cứ lúc nào, em luôn sẵn sàng hỗ trợ ạ.",
         "zh": "这是我就{product}最后一次联系，以免打扰{company}。今后如有需要，欢迎随时联系，我随时为您服务。",
         "en": "This is my last note on {product} so as not to disturb {company}. Whenever a need arises, please message me — I'm always happy to help."},
}


def _slot(lang_dict=True):
    d = date.today() + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return {"slot_vi": f"14:00 ngày {d.strftime('%d/%m')}", "slot_zh": f"{d.month}月{d.day}日下午2点", "slot_en": f"2pm on {d.strftime('%d %b')}"}


def suggest_text(intent: str, lang: str, cust: dict, product: Optional[str], rm: str, bank: str) -> str:
    tpl = REPLIES.get(intent, REPLIES["other"]).get(lang) or REPLIES["other"]["vi"]
    pn = PRODUCTS[product][lang] if product in PRODUCTS and lang in PRODUCTS[product] else (PRODUCTS[product]["vi"] if product in PRODUCTS else {"vi": "giải pháp tài chính", "zh": "金融方案", "en": "financial solution"}[lang])
    company = (cust.get("name_zh") if lang == "zh" and cust.get("name_zh") else cust["name"])
    body = tpl.format(product=pn, company=company, **_slot())
    sign = {"vi": f"\nTrân trọng,\n{rm} – {bank}", "zh": f"\n此致\n{rm}｜{bank}", "en": f"\nBest regards,\n{rm} | {bank}"}[lang]
    return body + sign


# ── trạng thái hội thoại ─────────────────────────────────────────────────────
STATUS_LABEL = {"HOT": "🔥 Nóng", "ENGAGED": "💬 Đang trao đổi", "OBJECTION": "⚠️ Có phản đối", "WAITING": "⏳ Chờ phản hồi",
                "NO_REPLY": "🔕 Chưa phản hồi", "CONVERTED": "✅ Chuyển đổi", "OPTOUT": "⛔ Từ chối nhận tin"}


def _thread_status(msgs, opt_out: bool, converted: bool, now: datetime) -> str:
    if opt_out:
        return "OPTOUT"
    if converted:
        return "CONVERTED"
    ins = [m for m in msgs if m.direction == "in"]
    outs = [m for m in msgs if m.direction == "out"]
    if ins:
        last_in = ins[-1]
        if outs and outs[-1].created_at > last_in.created_at and (now - outs[-1].created_at).days >= 7:
            return "NO_REPLY"
        if last_in.intent in HOT:
            return "HOT"
        if last_in.intent in OBJECTION:
            return "OBJECTION"
        return "ENGAGED"
    if outs:
        return "NO_REPLY" if (now - outs[-1].created_at).days >= 3 else "WAITING"
    return "WAITING"


def _msg(m: CorpMessage):
    return {"id": m.id, "direction": m.direction, "channel": m.channel, "language": m.language, "subject": m.subject, "body": m.body,
            "intent": m.intent, "intent_label": INTENT_LABEL.get(m.intent) if m.intent else None, "product": m.product,
            "created_by": m.created_by, "created_at": m.created_at.isoformat() + "Z", "campaign_id": m.campaign_id}


def _threads(db, user):
    custs = {c.customer_id: c for c in rm_filter(db.query(CorpCustomer), user)}
    by = {}
    for m in db.query(CorpMessage).order_by(CorpMessage.created_at):
        if m.customer_id in custs:
            by.setdefault(m.customer_id, []).append(m)
    optout = {r.customer_id for r in db.query(CorpOptOut)}
    conv = {(o.customer_id, o.product) for o in db.query(CorpOpportunity).filter(CorpOpportunity.stage == "Triển khai")}
    won_targets = {(t.customer_id) for t in db.query(CorpCampaignTarget).filter(CorpCampaignTarget.status == "Chuyển đổi")}
    now = datetime.utcnow()
    out = []
    for cid, msgs in by.items():
        c = custs[cid]
        prods = {m.product for m in msgs if m.product}
        converted = cid in won_targets or any((cid, p) in conv for p in prods)
        st = _thread_status(msgs, cid in optout, converted, now)
        last = msgs[-1]
        out.append({"customer_id": cid, "name": c.name, "contact_name": c.contact_name, "segment": c.segment, "rm_name": c.rm_name,
                    "language": c.preferred_language, "status": st, "status_label": STATUS_LABEL[st], "count": len(msgs),
                    "product": next((m.product for m in reversed(msgs) if m.product), None),
                    "last": {"direction": last.direction, "body": last.body[:140], "created_at": last.created_at.isoformat() + "Z",
                             "intent": last.intent, "intent_label": INTENT_LABEL.get(last.intent) if last.intent else None}})
    out.sort(key=lambda t: t["last"]["created_at"], reverse=True)
    return out


@router.get("/conversations")
def conversations(status: Optional[str] = None, q: Optional[str] = None, user=Depends(current_user)):
    db = SessionLocal()
    try:
        ts = _threads(db, user)
        counts = {k: 0 for k in STATUS_LABEL}
        for t in ts:
            counts[t["status"]] += 1
        if status and status != "ALL":
            ts = [t for t in ts if t["status"] == status]
        if q:
            ql = q.lower()
            ts = [t for t in ts if ql in t["name"].lower() or ql in (t["contact_name"] or "").lower() or ql in t["customer_id"].lower()]
        contacted = len({t["customer_id"] for t in _threads(db, user)})
        return {"items": ts, "counts": counts, "labels": STATUS_LABEL, "total": sum(counts.values()), "contacted": contacted}
    finally:
        db.close()


def _suggest_for(db, user, cid, msgs, override_msg=None, override_intent=None):
    c, _ = _get_one(db, cid, user)
    cfg = get_settings(db)
    last_in = next((m for m in reversed(msgs) if m.direction == "in"), None)
    text = override_msg if override_msg is not None else (last_in.body if last_in else "")
    intent = override_intent or (classify(text) if text else None)
    product = next((m.product for m in reversed(msgs) if m.product), None)
    lang = detect_lang(text, c.get("preferred_language") or "vi") if text else (c.get("preferred_language") or "vi")
    if not intent:
        return None
    return {"intent": intent, "intent_label": INTENT_LABEL[intent], "language": lang, "product": product,
            "text": suggest_text(intent, lang, c, product, user.full_name, cfg["bank_name"])}


@router.get("/conversations/{cid}")
def conversation(cid: str, user=Depends(current_user)):
    db = SessionLocal()
    try:
        c, ms = _get_one(db, cid, user)
        msgs = db.query(CorpMessage).filter_by(customer_id=cid).order_by(CorpMessage.created_at).all()
        th = next((t for t in _threads(db, user) if t["customer_id"] == cid), None)
        opps = [{"id": o.id, "product": o.product, "product_name": PRODUCTS[o.product]["vi"], "stage": o.stage} for o in db.query(CorpOpportunity).filter_by(customer_id=cid)]
        opted = db.query(CorpOptOut).filter_by(customer_id=cid).first()
        mt = scoring.metrics(c, ms)
        return {"customer": {k: c[k] for k in ("customer_id", "name", "name_zh", "segment", "ownership", "industry", "province", "contact_name",
                                               "contact_title", "contact_phone", "contact_email", "preferred_language", "rm_name", "debt_group")},
                "status": th["status"] if th else "WAITING", "status_label": STATUS_LABEL[th["status"]] if th else STATUS_LABEL["WAITING"],
                "messages": [_msg(m) for m in msgs], "suggestion": _suggest_for(db, user, cid, msgs), "opportunities": opps,
                "opted_out": bool(opted), "opt_reason": opted.reason if opted else None,
                "product_options": [{"code": k, "vi": v["vi"]} for k, v in PRODUCTS.items()]}
    finally:
        db.close()


class MsgIn(BaseModel):
    direction: str          # in | out
    body: str
    channel: str = "zalo"
    product: Optional[str] = None
    subject: Optional[str] = None


@router.post("/conversations/{cid}/messages")
def add_message(cid: str, body: MsgIn, request: Request, user=Depends(current_user)):
    if body.direction not in ("in", "out") or not body.body.strip():
        raise HTTPException(400, "Nội dung tin nhắn không hợp lệ")
    if body.product and body.product not in PRODUCTS:
        raise HTTPException(400, "Sản phẩm không hợp lệ")
    db = SessionLocal()
    try:
        c = get_customer_or_403(db, user, cid)
        prev = db.query(CorpMessage).filter_by(customer_id=cid).order_by(CorpMessage.created_at).all()
        last_out = next((m for m in reversed(prev) if m.direction == "out"), None)
        product = body.product or (last_out.product if last_out else None)
        camp = last_out.campaign_id if last_out else None
        intent = classify(body.body) if body.direction == "in" else None
        m = CorpMessage(customer_id=cid, campaign_id=camp, direction=body.direction, channel=body.channel, subject=body.subject,
                        body=body.body.strip(), intent=intent, product=product, created_by=user.username,
                        language=detect_lang(body.body, c.preferred_language or "vi"))
        db.add(m)
        effects = []
        now = datetime.utcnow()
        if body.direction == "in":
            c.last_contact_date = date.today()
            db.add(CorpInteraction(customer_id=cid, date=date.today(), channel={"zalo": "Zalo", "email": "Email", "call": "Điện thoại"}.get(body.channel, body.channel),
                                   summary=f"Khách phản hồi: {INTENT_LABEL[intent]}", outcome=INTENT_LABEL[intent]))
            tgt = db.query(CorpCampaignTarget).filter(CorpCampaignTarget.customer_id == cid, CorpCampaignTarget.campaign_id == camp).first() if camp else None
            if tgt and tgt.status in ("Chưa liên hệ", "Đã liên hệ", "Phản hồi", "Quan tâm"):
                new = "Từ chối" if intent in ("optout", "noneed") else "Quan tâm" if intent in HOT else "Phản hồi"
                rank = {"Chưa liên hệ": 0, "Đã liên hệ": 1, "Phản hồi": 2, "Quan tâm": 3}
                if new == "Từ chối" or rank.get(new, 0) > rank.get(tgt.status, 0):
                    tgt.status, tgt.updated_at = new, now
                    effects.append(f"Chiến dịch: {new}")
            if intent == "optout":
                if not db.query(CorpOptOut).filter_by(customer_id=cid).first():
                    db.add(CorpOptOut(customer_id=cid, reason=body.body.strip()[:200], created_by=user.username))
                effects.append("Đã thêm vào danh sách từ chối nhận tin")
            if intent in HOT and product:
                opp = db.query(CorpOpportunity).filter(CorpOpportunity.customer_id == cid, CorpOpportunity.product == product,
                                                       CorpOpportunity.stage.notin_(["Thất bại", "Triển khai"])).first()
                if opp and opp.stage == "Tiếp cận":
                    opp.stage, opp.probability, opp.updated_at = "Đang tư vấn", STAGE_PROB["Đang tư vấn"], now
                    effects.append("Cơ hội chuyển sang 'Đang tư vấn'")
        else:
            c.last_contact_date = date.today()
        db.commit()
        db.refresh(m)
        msgs = db.query(CorpMessage).filter_by(customer_id=cid).order_by(CorpMessage.created_at).all()
        audit(user, f"message.{body.direction}", "customer", cid, intent or "", client_ip(request))
        return {"message": _msg(m), "effects": effects, "suggestion": _suggest_for(db, user, cid, msgs) if body.direction == "in" else None}
    finally:
        db.close()


class SuggestIn(BaseModel):
    intent: Optional[str] = None
    language: Optional[str] = None
    use_llm: bool = False


@router.post("/conversations/{cid}/suggest")
def suggest(cid: str, body: SuggestIn, user=Depends(current_user)):
    if body.intent and body.intent not in INTENT_LABEL:
        raise HTTPException(400, "Ý định không hợp lệ")
    db = SessionLocal()
    try:
        c, _ = _get_one(db, cid, user)
        msgs = db.query(CorpMessage).filter_by(customer_id=cid).order_by(CorpMessage.created_at).all()
        s = _suggest_for(db, user, cid, msgs, override_intent=body.intent) or {
            "intent": "other", "intent_label": INTENT_LABEL["other"], "language": c.get("preferred_language") or "vi", "product": None,
            "text": suggest_text("other", c.get("preferred_language") or "vi", c, None, user.full_name, get_settings(db)["bank_name"])}
        if body.language in ("vi", "zh", "en"):
            s["language"] = body.language
            s["text"] = suggest_text(s["intent"], body.language, c, s["product"], user.full_name, get_settings(db)["bank_name"])
        s["llm_used"], s["llm_error"] = False, None
        if body.use_llm and get_settings(db)["llm_enabled"]:
            last_in = next((m for m in reversed(msgs) if m.direction == "in"), None)
            prompt = ("Bạn là chuyên viên quan hệ khách hàng doanh nghiệp tại ngân hàng. Hãy viết lại bản nháp trả lời dưới đây cho tự nhiên, lịch sự, ngắn gọn "
                      f"(giữ nguyên ngôn ngữ: {s['language']}). KHÔNG thêm số liệu, lãi suất, hạn mức hay cam kết phê duyệt.\n\n"
                      f"Tin nhắn của khách: {last_in.body if last_in else '(chưa có)'}\n\nBản nháp:\n{s['text']}")
            txt, err = agent.llm_complete(prompt, max_tokens=400)
            if txt:
                s["text"], s["llm_used"] = txt, True
            s["llm_error"] = err
        return s
    finally:
        db.close()


@router.post("/conversations/{cid}/optout")
def toggle_optout(cid: str, body: dict, request: Request, user=Depends(current_user)):
    db = SessionLocal()
    try:
        get_customer_or_403(db, user, cid)
        row = db.query(CorpOptOut).filter_by(customer_id=cid).first()
        if body.get("opt_out"):
            if not row:
                db.add(CorpOptOut(customer_id=cid, reason=str(body.get("reason") or "RM ghi nhận")[:200], created_by=user.username))
        elif row:
            if user.role != "admin":
                raise HTTPException(403, "Chỉ Admin được gỡ khách khỏi danh sách từ chối nhận tin")
            db.delete(row)
        db.commit()
        audit(user, "optout.set" if body.get("opt_out") else "optout.clear", "customer", cid, None, client_ip(request))
        return {"ok": True}
    finally:
        db.close()


@router.get("/followups/due")
def followups_due(user=Depends(current_user)):
    """Khách đã nhận tin nhưng chưa phản hồi: nhắc theo nhịp 3 / 7 / 14 ngày."""
    db = SessionLocal()
    try:
        cfg = get_settings(db)
        custs = {c.customer_id: c for c in rm_filter(db.query(CorpCustomer), user)}
        optout = {r.customer_id for r in db.query(CorpOptOut)}
        by = {}
        for m in db.query(CorpMessage).order_by(CorpMessage.created_at):
            if m.customer_id in custs:
                by.setdefault(m.customer_id, []).append(m)
        now = datetime.utcnow()
        rows = []
        for cid, msgs in by.items():
            if cid in optout or msgs[-1].direction != "out":
                continue
            age = (now - msgs[-1].created_at).days
            step = 14 if age >= 14 else 7 if age >= 7 else 3 if age >= 3 else None
            if step is None:
                continue
            c = custs[cid]
            lang = c.preferred_language or "vi"
            cd = {"name": c.name, "name_zh": c.name_zh}
            prod = msgs[-1].product
            pn = PRODUCTS[prod][lang] if prod in PRODUCTS else {"vi": "giải pháp tài chính", "zh": "金融方案", "en": "financial solution"}[lang]
            text = FOLLOWUP[step][lang].format(product=pn, company=(c.name_zh if lang == "zh" and c.name_zh else c.name))
            rows.append({"customer_id": cid, "name": c.name, "days": age, "step": step, "product": prod, "language": lang,
                         "text": text + {"vi": f"\nTrân trọng, {user.full_name}", "zh": f"\n{user.full_name}", "en": f"\nBest, {user.full_name}"}[lang]})
        rows.sort(key=lambda r: -r["days"])
        return {"items": rows[:30], "total": len(rows)}
    finally:
        db.close()
