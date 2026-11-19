"""Kiểm thử tra cứu MST: phân tích hồ sơ, khớp đúng MST, dừng khi bị chặn, chỉ điền ô trống."""
import types
from src.corporate import lookup as L

HTML = """<html><body><h1>0301234567 - CÔNG TY TNHH ABC</h1>
<table class="table-taxinfo"><thead><tr><th colspan=2>0301234567 - CÔNG TY TNHH ABC</th></tr></thead><tbody>
<tr><td>Mã số thuế</td><td>0301234567</td></tr>
<tr><td>Địa chỉ</td><td>12 Nguyễn Huệ, Quận 1, TP. Hồ Chí Minh</td></tr>
<tr><td>Người đại diện</td><td><a href="/x">NGUYỄN VĂN AN</a></td></tr>
<tr><td>Điện thoại</td><td>0283 3822 114 Ẩn số điện thoại</td></tr>
<tr><td>Tình trạng</td><td>Đang hoạt động</td></tr></tbody></table></body></html>"""


class R:
    def __init__(self, url, text, code=200): self.url, self.text, self.status_code = url, text, code


class S:
    def __init__(self, resp): self.resp, self.headers = resp, {}
    def get(self, url, **k): return self.resp


def test_parse_match():
    p = L.parse_profile(HTML, "0301234567")
    assert p["representative"] == "NGUYỄN VĂN AN" and p["operating_status"] == "Đang hoạt động"
    assert p["phone"] == "02833822114" and "Quận 1" in p["address"]


def test_parse_wrong_mst_rejected():
    assert L.parse_profile(HTML, "0309999999") is None


def test_lookup_ok_and_wrong_page():
    ok = L.lookup_mst("0301234567", S(R("https://masothue.com/0301234567-cong-ty-tnhh-abc", HTML)))
    assert ok["status"] == "matched" and ok["source_url"].startswith("https://masothue.com/0301234567-")
    # trang redirect sang doanh nghiệp khác → không nhận
    bad = L.lookup_mst("0301234567", S(R("https://masothue.com/0300000001-cong-ty-khac", HTML)))
    assert bad["status"] == "not_found"


def test_blocked_and_bad_mst():
    assert L.lookup_mst("0301234567", S(R("https://masothue.com/x", "", 429)))["status"] == "blocked"
    assert L.lookup_mst("0301234567", S(R("https://masothue.com/x", "<html>Just a moment...</html>")))["status"] == "blocked"
    assert L.lookup_mst("abc")["status"] == "bad_mst"


def test_apply_only_blank():
    c = types.SimpleNamespace(contact_name="Trần B", contact_title="KTT", contact_phone=None)
    f = L.apply_to_customer(None, c, {"status": "matched", "representative": "NGUYỄN VĂN AN", "phone": "02833822114"})
    assert c.contact_name == "Trần B" and c.contact_title == "KTT" and c.contact_phone == "02833822114" and f == ["contact_phone"]
    c2 = types.SimpleNamespace(contact_name=None, contact_title=None, contact_phone=None)
    L.apply_to_customer(None, c2, {"status": "matched", "representative": "NGUYỄN VĂN AN", "phone": ""})
    assert c2.contact_name == "NGUYỄN VĂN AN" and c2.contact_title == "GD"
