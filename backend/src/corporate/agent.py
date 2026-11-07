"""Natural-language assistant for corporate RMs (Vietnamese / English / Chinese keywords).

Pipeline: parse intent → filter customers → rank → (optional) draft messages → summarise.
The parsing/ranking is deterministic and explainable; an LLM (if configured) only writes the final summary."""
import re
import unicodedata

from .catalog import PRODUCTS, INDUSTRIES


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


COUNTRY_KW = {
    "Trung Quốc": ["trung quoc", "china", "中国", "大陆", "chinese"],
    "Đài Loan": ["dai loan", "taiwan", "台湾", "台灣"],
    "Hàn Quốc": ["han quoc", "korea", "韩国"],
    "Nhật Bản": ["nhat ban", "japan", "日本"],
    "Singapore": ["singapore", "sing "],
}
INDUSTRY_KW = {
    "Dệt may – Da giày": ["det may", "may mac", "da giay", "textile", "garment", "footwear", "纺织", "服装"],
    "Điện tử – Linh kiện": ["dien tu", "linh kien", "electronic", "电子"],
    "Cơ khí chế tạo": ["co khi", "che tao", "machinery", "机械"],
    "Nhựa – Bao bì": ["nhua", "bao bi", "plastic", "packaging", "塑胶"],
    "Thực phẩm – Đồ uống": ["thuc pham", "do uong", "food", "beverage", "食品"],
    "Gỗ – Nội thất": ["go ", "noi that", "furniture", "wood", "家具", "木"],
    "Logistics – Vận tải": ["logistics", "van tai", "kho van", "物流"],
    "Xây dựng – Hạ tầng": ["xay dung", "ha tang", "construction", "建筑"],
    "Thương mại XNK": ["thuong mai", "trading", "贸易"],
    "Hóa chất – Phân bón": ["hoa chat", "phan bon", "chemical", "化工"],
    "Nông sản – Thủy sản": ["nong san", "thuy san", "seafood", "agri", "水产"],
    "Vật liệu xây dựng": ["vat lieu", "xi mang", "building material", "建材"],
    "Năng lượng tái tạo": ["nang luong", "dien mat troi", "solar", "renewable", "太阳能"],
    "Phát triển hạ tầng KCN": ["kcn", "khu cong nghiep", "industrial park", "bat dong san cong nghiep", "工业区"],
}
PROVINCE_KW = {
    "TP. Hồ Chí Minh": ["ho chi minh", "hcm", "sai gon", "tphcm", "胡志明"],
    "Bình Dương": ["binh duong", "平阳"],
    "Đồng Nai": ["dong nai", "同奈"],
    "Long An": ["long an", "隆安"],
    "Bà Rịa – Vũng Tàu": ["vung tau", "ba ria", "头顿"],
    "Bắc Ninh": ["bac ninh", "北宁"],
    "Hải Phòng": ["hai phong", "海防"],
    "Hưng Yên": ["hung yen"],
    "Tây Ninh": ["tay ninh", "西宁"],
}
PRODUCT_KW = {
    "UPAS": ["upas"],
    "LC": [" l/c", "lc ", "thu tin dung", "letter of credit", "信用证"],
    "BAO_LANH": ["bao lanh", "guarantee", "保函"],
    "VAY_VLD": ["von luu dong", "vay von", "working capital", "tin dung", "vay ", "流动资金"],
    "VAY_DT": ["vay dau tu", "tai tro du an", "du an", "mo rong san xuat", "capex", "投资贷款"],
    "NGOAI_TE": ["ngoai te", "ty gia", "hedging", "phong ngua", "fx", "外汇", "汇率"],
    "LUONG": ["chi luong", "luong", "payroll", "thẻ", "the luong", "代发"],
    "DONG_TIEN": ["dong tien", "cash management", "thu ho", "chi ho", "ibanking", "现金管理"],
    "TIEN_GUI": ["tien gui", "casa", "huy dong", "deposit", "存款"],
    "TTQT": ["ttqt", "thanh toan quoc te", "xuat nhap khau", "xuat khau", "international payment", "国际结算"],
}
RISK_KW = {
    "HET_HAN_MUC": ["het han han muc", "gia han", "tai cap", "sap het han", "limit expir", "renew", "到期"],
    "DOANH_SO_GIAM": ["doanh so giam", "dong tien giam", "sut giam", "giam doanh so", "inflow drop"],
    "NHOM_NO": ["nhom no", "no xau", "qua han", "npl"],
    "SU_DUNG_CAO": ["su dung han muc cao", "dung het han muc", "tang han muc", "high utilization"],
    "CASA_GIAM": ["casa giam", "chuyen dong tien", "churn", "roi bo"],
}
DRAFT_KW = ["soan", "viet tin", "tin nhan", "email", "zalo", "draft", "message", "kich ban", "script", "草拟", "发送", "邮件", "话术"]
LANG_KW = {"zh": ["tieng trung", "中文", "chinese", "tieng hoa"], "en": ["tieng anh", "english"], "vi": ["tieng viet", "vietnamese"]}


def parse_query(q: str) -> dict:
    n = " " + _norm(q) + " "
    raw = q.lower()

    def hit(kws):
        return any((k in n) or (k in raw) for k in kws)

    f = {"ownership": None, "country": None, "industry": None, "province": None,
         "product": None, "risk": None, "draft": False, "channel": "zalo", "language": None,
         "limit": 8, "segment": None, "tier": None}
    if hit(["fdi", "nuoc ngoai", "von ngoai", "外资"]):
        f["ownership"] = "FDI"
    elif hit(["noi dia", "trong nuoc", "viet nam thuan", "domestic"]):
        f["ownership"] = "Nội địa"
    for k, kws in COUNTRY_KW.items():
        if hit(kws):
            f["country"] = k; f["ownership"] = "FDI"; break
    for k, kws in INDUSTRY_KW.items():
        if hit(kws):
            f["industry"] = k; break
    for k, kws in PROVINCE_KW.items():
        if hit(kws):
            f["province"] = k; break
    for k, kws in RISK_KW.items():
        if hit(kws):
            f["risk"] = k; break
    for k in ["UPAS", "LC", "BAO_LANH", "NGOAI_TE", "LUONG", "DONG_TIEN", "TIEN_GUI", "TTQT", "VAY_DT", "VAY_VLD"]:
        if hit(PRODUCT_KW[k]):
            f["product"] = k; break
    if f["risk"] == "HET_HAN_MUC" and f["product"] in (None, "VAY_VLD"):
        f["product"] = None
    f["draft"] = hit(DRAFT_KW)
    if hit(["email", "邮件", "thu dien tu"]):
        f["channel"] = "email"
    if hit(["kich ban", "goi dien", "script", "cuoc goi", "话术"]):
        f["channel"] = "call"
    for lang, kws in LANG_KW.items():
        if hit(kws):
            f["language"] = lang; break
    if hit(["sme", "doanh nghiep nho"]):
        f["segment"] = "SME"
    elif hit(["middle", "doanh nghiep vua", "trung binh"]):
        f["segment"] = "Middle"
    elif hit(["large", "doanh nghiep lon", "tap doan"]):
        f["segment"] = "Large"
    if hit(["hang a", "tier a", "khach hang lon nhat", "khach hang chien luoc"]):
        f["tier"] = "A"
    m = re.search(r"top\s*(\d{1,2})|(\d{1,2})\s*(?:khach|doanh nghiep|dn\b|cong ty|company|companies|customers|家)", n)
    if m:
        f["limit"] = max(1, min(25, int(m.group(1) or m.group(2))))
    return f


def describe_filters(f: dict) -> list:
    out = []
    if f["ownership"]:
        out.append(f"Loại hình: {f['ownership']}")
    if f["country"]:
        out.append(f"Quốc gia đầu tư: {f['country']}")
    if f["industry"]:
        out.append(f"Ngành: {f['industry']}")
    if f["province"]:
        out.append(f"Tỉnh/TP: {f['province']}")
    if f["segment"]:
        out.append(f"Phân khúc: {f['segment']}")
    if f["tier"]:
        out.append(f"Hạng: {f['tier']}")
    if f["product"]:
        out.append(f"Sản phẩm: {PRODUCTS[f['product']]['vi']}")
    if f["risk"]:
        out.append(f"Cảnh báo: {f['risk']}")
    return out or ["Toàn bộ danh mục"]


def apply(f: dict, items: list) -> list:
    """items: [{'c': customer_dict, 'a': analysis}]"""
    res = []
    for it in items:
        c, a = it["c"], it["a"]
        if f["ownership"] and c["ownership"] != f["ownership"]:
            continue
        if f["country"] and c["investor_country"] != f["country"]:
            continue
        if f["industry"] and c["industry"] != f["industry"]:
            continue
        if f["province"] and c["province"] != f["province"]:
            continue
        if f["segment"] and c["segment"] != f["segment"]:
            continue
        if f["tier"] and a["tier"] != f["tier"]:
            continue
        if f["risk"] and not any(x["code"] == f["risk"] for x in a["risk_flags"]):
            continue
        if f["product"]:
            p = a["propensities"][f["product"]]
            if p["score"] < 40:
                continue
        res.append(it)
    if f["product"]:
        res.sort(key=lambda it: -it["a"]["propensities"][f["product"]]["score"])
    elif f["risk"]:
        sev = {"high": 2, "medium": 1, "low": 0}
        res.sort(key=lambda it: -max(sev[x["severity"]] for x in it["a"]["risk_flags"]) * 1000 - it["a"]["priority_score"])
    else:
        res.sort(key=lambda it: -it["a"]["priority_score"])
    return res


def template_answer(f: dict, total: int, shown: list) -> str:
    desc = "; ".join(describe_filters(f))
    if not shown:
        return f"Không tìm thấy doanh nghiệp phù hợp với tiêu chí ({desc}). Hãy thử nới điều kiện lọc."
    names = ", ".join(s["name"] for s in shown[:3])
    first = shown[0]
    why = first.get("headline") or ""
    return (f"Tìm thấy {total} doanh nghiệp phù hợp ({desc}); hiển thị {len(shown)} ưu tiên cao nhất. "
            f"Dẫn đầu: {names}. Ưu tiên số 1 — {first['name']}: {why}")


def llm_complete(prompt: str, max_tokens: int = 500, temperature: float = 0.3):
    """Gọi LLM đã cấu hình (Gemini / NVIDIA / Ollama). Trả về (text|None, lỗi|None)."""
    try:
        from src.config import settings
        from src.llm.base import LLMMessage
        backend = settings.llm_backend
        if backend == "gemini":
            if not settings.gemini_api_key:
                return None, "Chưa cấu hình GEMINI_API_KEY"
            from src.llm.gemini import GeminiProvider
            prov = GeminiProvider()
        elif backend == "nvidia":
            if not settings.nvidia_api_key:
                return None, "Chưa cấu hình NVIDIA_API_KEY"
            from src.llm.nvidia import NvidiaProvider
            prov = NvidiaProvider()
        else:
            from src.llm.ollama import OllamaProvider
            prov = OllamaProvider()
        text = prov.complete([LLMMessage(role="user", content=prompt)], temperature=temperature, max_tokens=max_tokens)
        return (text or "").strip() or None, None
    except Exception as e:  # noqa: BLE001 — luôn có phương án dự phòng
        return None, f"{type(e).__name__}: {str(e)[:160]}"


def llm_summary(query: str, f: dict, total: int, shown: list):
    """Optional LLM polish. Returns (text|None, error|None)."""
    rows = "\n".join(
        f"- {s['name']} ({s['ownership']}{', ' + s['investor_country'] if s['investor_country'] else ''}, {s['industry']}, {s['province']}): "
        f"{s.get('headline','')}" for s in shown[:6])
    prompt = (
        "Bạn là trợ lý cho Giám đốc/chuyên viên quan hệ khách hàng doanh nghiệp tại ngân hàng. "
        "Dựa CHỈ trên dữ liệu dưới đây, viết tóm tắt 3-5 câu tiếng Việt: nêu nhóm khách hàng, 2-3 doanh nghiệp nên ưu tiên và hành động tiếp theo. "
        "Không bịa số liệu, không hứa hạn mức/lãi suất.\n\n"
        f"Yêu cầu của RM: {query}\nTiêu chí đã áp dụng: {'; '.join(describe_filters(f))}\nTổng số phù hợp: {total}\nDanh sách:\n{rows}"
    )
    return llm_complete(prompt)
