"""Outreach drafts for corporate customers: Zalo / Email / Call script, in vi / zh / en.

Drafts are templates filled with the customer's real numbers. No rates or approvals are promised."""
import os
from datetime import datetime

from .catalog import PRODUCTS, TITLES

BANK_NAME = os.getenv("CORP_BANK_NAME", "TPBank")


# ── number formatting per language ───────────────────────────────────────────
def _num(x, d=1, lang="vi"):
    s = f"{x:,.{d}f}"
    if lang == "vi":
        s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s


def fmt_usd(m, lang):
    if lang == "zh":
        return f"约{m * 100:,.0f}万美元"
    if lang == "en":
        return f"~USD {_num(m, 1, 'en')}M"
    return f"khoảng {_num(m, 1)} triệu USD"


def fmt_bn(bn, lang):
    if lang == "zh":
        return f"约{bn * 10:,.0f}亿越南盾"
    if lang == "en":
        return f"~VND {_num(bn, 1, 'en')}bn"
    return f"khoảng {_num(bn, 1)} tỷ đồng"


def fmt_date(d, lang):
    if not d:
        return "—"
    if isinstance(d, str):
        d = datetime.fromisoformat(d).date()
    if lang == "zh":
        return f"{d.year}年{d.month}月{d.day}日"
    if lang == "en":
        return d.strftime("%d %b %Y")
    return d.strftime("%d/%m/%Y")


# ── templates ────────────────────────────────────────────────────────────────
T = {
 "LC": {
  "vi": dict(subject="Giải pháp thanh toán nhập khẩu bằng L/C cho {company}",
    hook="Em thấy {company} nhập khẩu {imp}/năm. Với quy mô này, L/C giúp thanh toán an toàn với nhà cung cấp nước ngoài và tận dụng thời hạn trả chậm.",
    bullets=["Phát hành L/C nhanh, hỗ trợ kiểm tra chứng từ và tư vấn điều kiện Incoterms", "Có thể kết hợp tài trợ trả chậm (UPAS) để tối ưu chi phí vốn", "Một đầu mối RM xử lý trọn quy trình"],
    ask="Anh/Chị cho em xin 15 phút trao đổi kế hoạch nhập khẩu quý tới được không ạ?"),
  "zh": dict(subject="为{company_zh}定制的进口信用证(L/C)方案",
    hook="我们了解到贵司年进口额{imp}。在此规模下，信用证可保障与海外供应商的结算安全，并可争取更长的付款账期。",
    bullets=["快速开立信用证，协助审核单据并提供贸易术语建议", "可搭配UPAS远期融资，降低资金成本", "专属客户经理一站式跟进"],
    ask="方便占用您15分钟，沟通一下下季度的进口计划吗？"),
  "en": dict(subject="Import L/C solution for {company}",
    hook="We noticed {company} imports {imp} a year. At this scale an L/C secures payment to overseas suppliers and extends your payment terms.",
    bullets=["Fast L/C issuance with document checking and Incoterms guidance", "Optional usance funding (UPAS) to lower financing cost", "One dedicated RM for the whole process"],
    ask="Could we set up 15 minutes to discuss your import plan for next quarter?"),
 },
 "UPAS": {
  "vi": dict(subject="Tài trợ nhập khẩu UPAS L/C — tối ưu chi phí vốn cho {company}",
    hook="Kim ngạch nhập khẩu của {company} {imp}/năm. UPAS L/C cho phép thanh toán nhà cung cấp ngay, còn doanh nghiệp trả ngân hàng sau (thường 90–180 ngày) với chi phí vốn thường thấp hơn vay VND thông thường.",
    bullets=["Nhà cung cấp nhận tiền ngay, giữ quan hệ thương mại tốt", "Kéo dài chu kỳ vốn lưu động, giảm áp lực dòng tiền", "Phù hợp doanh nghiệp có doanh số nhập khẩu đều"],
    ask="Anh/Chị có thể chia sẻ kế hoạch nhập khẩu 6 tháng tới để em tính phương án cụ thể không ạ?"),
  "zh": dict(subject="UPAS远期信用证融资——降低{company_zh}的资金成本",
    hook="贵司年进口额{imp}。通过UPAS信用证，供应商可即期收款，贵司则在90–180天后向银行付款，融资成本通常低于一般越盾贷款。",
    bullets=["供应商即期收款，维护良好供货关系", "延长营运资金周期，缓解现金流压力", "适合进口业务稳定的企业"],
    ask="方便分享未来半年的进口计划吗？我们可据此设计具体方案。"),
  "en": dict(subject="UPAS L/C import financing for {company}",
    hook="{company} imports {imp} a year. With UPAS L/C your suppliers are paid at sight while you settle with the bank later (typically 90–180 days), often at a lower cost than VND borrowing.",
    bullets=["Suppliers get paid immediately, protecting the relationship", "Longer working-capital cycle and less cash-flow pressure", "Fits companies with steady import volumes"],
    ask="Could you share your import plan for the next six months so we can size a proposal?"),
 },
 "BAO_LANH": {
  "vi": dict(subject="Hạn mức bảo lãnh cho {company}",
    hook="Với đặc thù ngành {industry} và quy mô doanh thu {rev}/năm, {company} thường cần bảo lãnh (dự thầu, thực hiện hợp đồng, thanh toán). Một hạn mức bảo lãnh sẵn có giúp đội ngũ phản ứng nhanh khi có hợp đồng mới.",
    bullets=["Hạn mức bảo lãnh linh hoạt, phát hành trong thời gian ngắn", "Ký quỹ tối ưu theo hồ sơ tín dụng", "Hỗ trợ bảo lãnh cho đối tác trong và ngoài nước"],
    ask="Anh/Chị đang có hợp đồng/gói thầu nào cần bảo lãnh trong quý này không ạ?"),
  "zh": dict(subject="为{company_zh}设立保函额度",
    hook="鉴于{industry}行业特点及贵司{rev}的年营收，投标、履约和付款保函需求较多。预设保函额度可帮助贵司在新合同到来时快速响应。",
    bullets=["灵活的保函额度，出具时间短", "根据信用状况优化保证金比例", "支持境内外受益人保函"],
    ask="请问本季度是否有需要保函的合同或招标项目？"),
  "en": dict(subject="Bank guarantee facility for {company}",
    hook="Given the nature of {industry} and annual revenue of {rev}, {company} likely needs guarantees (bid, performance, payment). A ready facility lets your team respond quickly when new contracts arrive.",
    bullets=["Flexible guarantee limit with short issuance time", "Margin optimised to your credit profile", "Guarantees for domestic and overseas beneficiaries"],
    ask="Do you have any contract or tender this quarter that needs a guarantee?"),
 },
 "TTQT": {
  "vi": dict(subject="Thanh toán quốc tế nhanh và tiết kiệm cho {company}",
    hook="{company} có kim ngạch xuất nhập khẩu {trade}/năm. Chuyển sang xử lý thanh toán quốc tế tại ngân hàng giúp rút ngắn thời gian nhận/chuyển tiền và minh bạch phí.",
    bullets=["Chuyển/nhận tiền T/T nhanh, theo dõi trạng thái trực tuyến", "Tư vấn chứng từ và nhờ thu", "Biểu phí rõ ràng, ưu đãi theo doanh số"],
    ask="Anh/Chị cho em xin lịch ngắn để rà soát quy trình thanh toán quốc tế hiện tại nhé?"),
  "zh": dict(subject="为{company_zh}提供高效低成本的国际结算服务",
    hook="贵司年进出口总额{trade}。将国际结算集中办理，可缩短收付款时间，并使费用更透明。",
    bullets=["T/T汇款快速到账，可在线跟踪状态", "单据及托收业务咨询", "收费透明，按业务量给予优惠"],
    ask="方便约个短会，梳理一下目前的国际结算流程吗？"),
  "en": dict(subject="Faster, cheaper international payments for {company}",
    hook="{company} trades {trade} a year across borders. Centralising international payments with us shortens settlement time and makes fees transparent.",
    bullets=["Fast T/T with online status tracking", "Documentary collection and documents advice", "Clear tariff with volume-based discounts"],
    ask="Could we schedule a short review of your current international payment flow?"),
 },
 "NGOAI_TE": {
  "vi": dict(subject="Quản trị rủi ro tỷ giá cho {company}",
    hook="Trạng thái ngoại tệ của {company} ước tính {fx}. Biến động tỷ giá USD/VND có thể ảnh hưởng trực tiếp biên lợi nhuận; các công cụ kỳ hạn/hoán đổi giúp khóa tỷ giá cho các đơn hàng sắp tới.",
    bullets=["Mua bán ngoại tệ giao ngay với tỷ giá cạnh tranh", "Giao dịch kỳ hạn/hoán đổi để khóa chi phí", "Bản tin tỷ giá và tư vấn thời điểm giao dịch"],
    ask="Anh/Chị cho em xin 15 phút để mô phỏng tác động tỷ giá lên đơn hàng quý tới ạ?"),
  "zh": dict(subject="为{company_zh}管理汇率风险",
    hook="我们估计贵司的外汇敞口{fx}。美元/越盾汇率波动会直接影响利润率；远期及掉期工具可为未来订单锁定汇率。",
    bullets=["即期结售汇，汇率有竞争力", "远期/掉期交易锁定成本", "提供汇率资讯及交易时点建议"],
    ask="方便用15分钟，模拟一下汇率变动对下季度订单的影响吗？"),
  "en": dict(subject="FX risk management for {company}",
    hook="{company}'s FX exposure is estimated at {fx}. USD/VND moves hit margins directly; forwards and swaps can lock in rates for upcoming orders.",
    bullets=["Spot FX at competitive rates", "Forwards/swaps to lock in cost", "Rate bulletins and timing advice"],
    ask="Could we spend 15 minutes simulating the FX impact on next quarter's orders?"),
 },
 "LUONG": {
  "vi": dict(subject="Giải pháp chi lương & thẻ cho {emp} lao động của {company}",
    hook="{company} hiện có khoảng {emp} lao động. Chi lương qua tài khoản giúp tiết kiệm thời gian chi trả hằng tháng và mở ra các ưu đãi dành cho người lao động.",
    bullets=["Chi lương hàng loạt qua iBanking doanh nghiệp, đối soát tự động", "Mở tài khoản/thẻ cho người lao động ngay tại nhà máy", "Ưu đãi dành riêng cho nhân viên (thẻ, tiết kiệm, vay tiêu dùng)"],
    ask="Anh/Chị cho em xin lịch hẹn để trình bày phương án triển khai tại nhà máy ạ?"),
  "zh": dict(subject="为{company_zh}约{emp}名员工提供代发工资及员工卡方案",
    hook="贵司目前约有{emp}名员工。通过银行代发工资可节省每月发放时间，并为员工带来专属优惠。",
    bullets=["企业网银批量代发，自动对账", "可到工厂现场为员工开户办卡", "员工专属优惠(银行卡、储蓄、消费贷款)"],
    ask="方便预约时间，到工厂介绍实施方案吗？"),
  "en": dict(subject="Payroll & card programme for {company}'s {emp} employees",
    hook="{company} has around {emp} employees. Paying salaries through the bank saves monthly processing time and unlocks employee benefits.",
    bullets=["Bulk payroll via corporate internet banking with auto-reconciliation", "On-site account and card opening at your plant", "Employee-only offers (cards, savings, consumer loans)"],
    ask="Could we book a visit to present the roll-out plan at your site?"),
 },
 "DONG_TIEN": {
  "vi": dict(subject="Quản lý dòng tiền tự động cho {company}",
    hook="Dòng tiền về tài khoản của {company} {inflow}/tháng. Giải pháp thu hộ/chi hộ và đối soát tự động giúp kế toán giảm thao tác thủ công và nhìn thấy số dư theo thời gian thực.",
    bullets=["Thu hộ theo mã định danh (virtual account), đối soát tự động", "Chi hộ hàng loạt, phân quyền duyệt nhiều cấp", "Kết nối ERP/phần mềm kế toán"],
    ask="Anh/Chị cho em xin lịch demo 20 phút với bộ phận kế toán ạ?"),
  "zh": dict(subject="为{company_zh}提供自动化现金管理方案",
    hook="贵司账户月均资金流入{inflow}。代收代付与自动对账方案可减少财务人员手工操作，并实时掌握账户余额。",
    bullets=["虚拟账号代收，自动对账", "批量代付，多级审批授权", "可对接ERP/财务软件"],
    ask="方便与财务部门约一场20分钟的演示吗？"),
  "en": dict(subject="Automated cash management for {company}",
    hook="Inflows to {company}'s accounts average {inflow} a month. Automated collections/payments and reconciliation cut manual work and give real-time balances.",
    bullets=["Virtual-account collections with auto-reconciliation", "Bulk payments with multi-level approval", "ERP / accounting software integration"],
    ask="Could we schedule a 20-minute demo with your finance team?"),
 },
 "TIEN_GUI": {
  "vi": dict(subject="Tối ưu số dư nhàn rỗi cho {company}",
    hook="Số dư không kỳ hạn bình quân của {company} {casa}. Phần vốn nhàn rỗi có thể chuyển một phần sang tiền gửi có kỳ hạn linh hoạt để sinh lời mà vẫn giữ tính thanh khoản.",
    bullets=["Kỳ hạn linh hoạt từ 1 tuần, rút gốc linh hoạt", "Tự động chuyển số dư vượt mức sang tiền gửi", "Lãi suất theo biểu từng thời kỳ"],
    ask="Anh/Chị cho em xin 10 phút để rà soát kế hoạch dòng tiền và đề xuất phương án gửi phù hợp ạ?"),
  "zh": dict(subject="为{company_zh}优化闲置资金收益",
    hook="贵司活期日均余额{casa}。可将部分闲置资金转入灵活期限的定期存款，在保持流动性的同时增加收益。",
    bullets=["最短一周起存，提前支取灵活", "超额余额自动转存", "利率按各时期公布执行"],
    ask="方便用10分钟梳理资金计划，并提出合适的存款方案吗？"),
  "en": dict(subject="Put idle balances to work for {company}",
    hook="{company}'s average current-account balance is {casa}. Part of the idle funds can move into flexible term deposits to earn a return while keeping liquidity.",
    bullets=["Terms from one week, flexible early withdrawal", "Auto-sweep of balances above a threshold", "Rates per the prevailing tariff"],
    ask="Could we spend 10 minutes on your cash plan and suggest a suitable deposit set-up?"),
 },
 "VAY_VLD": {
  "vi": dict(subject="Đề xuất hạn mức vốn lưu động cho {company}",
    hook="Doanh số qua tài khoản của {company} đang tăng, và doanh thu {rev}/năm. Một hạn mức vốn lưu động phù hợp giúp chủ động mua nguyên vật liệu và đáp ứng đơn hàng mới.",
    bullets=["Hạn mức xoay vòng, giải ngân theo nhu cầu", "Quy trình thẩm định gọn, một đầu mối RM", "Có thể kết hợp bảo lãnh/L/C trong cùng hạn mức"],
    ask="Anh/Chị cho em xin lịch gặp để tìm hiểu kế hoạch sản xuất kinh doanh năm tới ạ?"),
  "zh": dict(subject="为{company_zh}设立流动资金额度的建议",
    hook="贵司账户流水持续增长，年营收{rev}。合适的流动资金额度有助于主动采购原材料并承接新订单。",
    bullets=["循环额度，按需提款", "审批流程精简，专属客户经理对接", "可在同一额度内叠加保函/信用证"],
    ask="方便约个时间，了解贵司明年的生产经营计划吗？"),
  "en": dict(subject="Working-capital facility proposal for {company}",
    hook="Account inflows at {company} are growing and revenue is {rev} a year. A suitable working-capital line helps you buy materials proactively and serve new orders.",
    bullets=["Revolving limit with drawdowns as needed", "Streamlined appraisal, one dedicated RM", "Can be combined with guarantees / L/C in one limit"],
    ask="Could we meet to understand your business plan for next year?"),
 },
 "VAY_VLD_RENEW": {
  "vi": dict(subject="Gia hạn / điều chỉnh hạn mức tín dụng của {company}",
    hook="Hạn mức của {company} sẽ hết hạn vào {expiry} (còn {days} ngày) và mức sử dụng hiện khoảng {util}. Em muốn chủ động chuẩn bị hồ sơ gia hạn, đồng thời xem xét điều chỉnh hạn mức theo nhu cầu mới.",
    bullets=["Danh mục hồ sơ cần chuẩn bị: BCTC, kế hoạch SXKD, hợp đồng đầu ra/đầu vào chính", "Em hỗ trợ rà soát hồ sơ trước để rút ngắn thời gian thẩm định", "Cân nhắc tăng hạn mức nếu có đơn hàng mới"],
    ask="Anh/Chị sắp xếp được buổi làm việc tuần này để em gửi checklist hồ sơ không ạ?"),
  "zh": dict(subject="{company_zh}授信额度续期/调整事宜",
    hook="贵司授信额度将于{expiry}到期(剩余{days}天)，目前使用率约{util}。我们希望提前准备续期材料，并根据新的业务需求评估调整额度。",
    bullets=["需准备材料：财务报表、经营计划、主要购销合同", "我们可提前协助审核材料，缩短审批时间", "如有新订单，可考虑提高额度"],
    ask="方便本周安排一次沟通，我们把材料清单发给您吗？"),
  "en": dict(subject="Renewal / adjustment of {company}'s credit limit",
    hook="{company}'s facility expires on {expiry} ({days} days left) and utilisation is about {util}. We would like to prepare the renewal early and review the limit against your new needs.",
    bullets=["Documents needed: financial statements, business plan, key sales/purchase contracts", "We can pre-review your file to shorten appraisal time", "Limit increase can be considered for new orders"],
    ask="Could we meet this week so I can send you the document checklist?"),
 },
 "VAY_DT": {
  "vi": dict(subject="Tài trợ đầu tư mở rộng cho {company}",
    hook="Ngành {industry} đang có nhiều cơ hội mở rộng, và {company} có vốn chủ sở hữu {equity}. Nếu đang có kế hoạch đầu tư máy móc/nhà xưởng, ngân hàng có thể đồng hành với khoản vay trung dài hạn.",
    bullets=["Vay trung dài hạn, thời gian ân hạn phù hợp dòng tiền dự án", "Tư vấn cơ cấu vốn và tài sản bảo đảm", "Kết hợp L/C nhập thiết bị và bảo lãnh thanh toán"],
    ask="Anh/Chị đang có kế hoạch đầu tư nào trong 12 tháng tới để em tìm hiểu thêm ạ?"),
  "zh": dict(subject="为{company_zh}扩产提供投资融资",
    hook="{industry}行业扩张机会较多，贵司净资产{equity}。如有设备或厂房投资计划，银行可提供中长期贷款支持。",
    bullets=["中长期贷款，宽限期匹配项目现金流", "提供资本结构及担保方案建议", "可搭配进口设备信用证及付款保函"],
    ask="请问未来12个月是否有投资计划？希望进一步了解。"),
  "en": dict(subject="Expansion financing for {company}",
    hook="{industry} has plenty of expansion opportunities and {company}'s equity is {equity}. If you plan machinery or plant investment, we can support with a medium/long-term loan.",
    bullets=["Medium/long-term loan with a grace period matched to project cash flow", "Advice on capital structure and collateral", "Combine with equipment-import L/C and payment guarantees"],
    ask="Do you have any investment plan in the next 12 months we could look at together?"),
 },
}

# Khung thuyết phục: thêm câu mở đầu / câu chốt (không đưa số liệu hay cam kết nào ngoài dữ liệu thật)
FRAMEWORKS = {
    "consultative": {"vi": "Tư vấn giải pháp", "en": "Consultative", "zh": "顾问式"},
    "aida": {"vi": "AIDA (Chú ý – Quan tâm – Mong muốn – Hành động)", "en": "AIDA", "zh": "AIDA"},
    "spin": {"vi": "SPIN (Tình huống – Vấn đề – Hệ quả – Nhu cầu)", "en": "SPIN", "zh": "SPIN"},
}
FW = {
    "aida": {
        "vi": dict(pre="Một thông tin có thể giúp {company} chủ động hơn về chi phí tài chính trong thời gian tới.\n",
                   post="Em có thể gửi đề xuất ngắn gọn trong 24 giờ để Anh/Chị xem trước. "),
        "zh": dict(pre="有一项信息或许能帮助{company_zh}更主动地管理近期的财务成本。\n",
                   post="我可在24小时内发送一份简要方案供您先行参考。"),
        "en": dict(pre="One point that may help {company} manage financing costs more proactively in the coming period.\n",
                   post="I can send a short proposal within 24 hours for your review. "),
    },
    "spin": {
        "vi": dict(pre="",
                   post="Hiện {company} đang xử lý nhu cầu này như thế nào, và có điểm nào chưa thuận tiện về thời gian hay chi phí không ạ? "
                        "Nếu có cách rút ngắn quy trình và tối ưu chi phí, Anh/Chị có muốn em trình bày không? "),
        "zh": dict(pre="",
                   post="目前{company_zh}是如何处理这一需求的？在时间或成本方面有没有不够顺畅的地方？如果有办法缩短流程并优化成本，您是否愿意听我介绍？"),
        "en": dict(pre="",
                   post="How is {company} handling this today, and is anything inconvenient in terms of time or cost? "
                        "If the process could be shorter and cheaper, would you like me to walk you through it? "),
    },
}

DISCLAIMER = {
    "vi": "(Hạn mức, lãi suất/phí ưu đãi áp dụng theo chính sách từng thời kỳ và kết quả thẩm định.)",
    "zh": "(额度及优惠利率/费用以银行政策及审批结果为准。)",
    "en": "(Limits, rates and fees are subject to prevailing policy and credit approval.)",
}

CALL = {
 "vi": dict(open="Mở đầu", disc="Câu hỏi khám phá", obj="Xử lý từ chối thường gặp", close="Kết thúc", hint="Gợi ý",
    open_t="Chào Anh/Chị {given}, em là {rm} bên {bank}, phụ trách {company}. Em gọi nhanh khoảng 3 phút, Anh/Chị tiện nghe máy không ạ?",
    disc_t=["Hiện tại {company} đang thanh toán/thu tiền chủ yếu qua những ngân hàng nào?", "Quý tới Anh/Chị có đơn hàng hay kế hoạch lớn nào cần chuẩn bị tài chính không?"],
    obj_t=[("\"Đã có ngân hàng khác lo rồi\"", "Em hiểu, em không đề nghị thay thế mà muốn bổ sung phần ngân hàng hiện tại chưa phục vụ tốt; mình thử một giao dịch nhỏ để so sánh."),
           ("\"Đang bận\"", "Dạ em xin 15 phút vào chiều nay hoặc sáng mai, em sẽ gửi sẵn tóm tắt qua Zalo để Anh/Chị xem trước."),
           ("\"Gửi thông tin qua email đi\"", "Dạ em gửi ngay, và xin phép gọi lại sau 2 ngày để giải đáp thắc mắc.")],
    close_t="Em chốt lịch {when}, và gửi tóm tắt qua Zalo/email ngay sau cuộc gọi. Cảm ơn Anh/Chị."),
 "zh": dict(open="开场", disc="探索性问题", obj="常见异议处理", close="结束语", hint="提示",
    open_t="{name}{title_zh}您好，我是{bank}负责{company_zh}的客户经理{rm}，占用您约3分钟，现在方便吗？",
    disc_t=["目前贵司主要通过哪些银行收付款？", "下季度是否有大订单或重大计划需要提前安排资金？"],
    obj_t=[("“已有合作银行”", "理解。我们并非要取代，而是补充现有银行服务不足的部分；可先做一笔小额业务对比体验。"),
           ("“现在比较忙”", "没问题，今天下午或明天上午我再约15分钟，并先通过微信/Zalo发送简要资料。"),
           ("“把资料发邮件吧”", "好的，我马上发送，并在两天后再跟进解答问题。")],
    close_t="那我们约定{when}，通话后立即发送摘要。谢谢您。"),
 "en": dict(open="Opening", disc="Discovery questions", obj="Common objections", close="Close", hint="Hint",
    open_t="Hello {given}, this is {rm} from {bank}, looking after {company}. I'll take about 3 minutes — is now a good time?",
    disc_t=["Which banks do you mainly use for collections and payments today?", "Any big orders or plans next quarter that need financing prepared?"],
    obj_t=[("\"We already have a bank\"", "Understood — I'm not asking to replace them, just to cover what they don't serve well. Let's try one small transaction to compare."),
           ("\"I'm busy\"", "No problem — 15 minutes this afternoon or tomorrow morning, and I'll send a summary first."),
           ("\"Just email me\"", "Sure, sending it now; I'll follow up in two days to answer questions.")],
    close_t="Let's lock in {when}; I'll send a summary right after this call. Thank you."),
}


def _given(name: str) -> str:
    return (name or "").split()[-1] if name else ""


def build_facts(c: dict, mt: dict, lang: str) -> dict:
    return {
        "company": c["name"],
        "company_zh": c.get("name_zh") or c["name"],
        "industry": c["industry"],
        "imp": fmt_usd(c["import_usd_m"], lang),
        "exp": fmt_usd(c["export_usd_m"], lang),
        "trade": fmt_usd(c["import_usd_m"] + c["export_usd_m"], lang),
        "fx": fmt_usd(c["fx_exposure_usd_m"], lang),
        "emp": f"{c['employees']:,}" if lang != "vi" else f"{c['employees']:,}".replace(",", "."),
        "rev": fmt_bn(c["annual_revenue_bn"], lang),
        "equity": fmt_bn(c["equity_bn"], lang),
        "casa": fmt_bn(c["casa_balance_bn"], lang),
        "inflow": fmt_bn(mt["avg_monthly_inflow_bn"], lang),
        "util": f"{(mt['utilization'] or 0) * 100:.0f}%",
        "days": mt["days_to_expiry"] if mt["days_to_expiry"] is not None else "—",
        "expiry": fmt_date(c.get("limit_expiry"), lang),
    }


def draft(c: dict, mt: dict, product: str, channel: str = "zalo", language: str | None = None,
          rm_name: str = "Chuyên viên QHKH", bank_name: str | None = None, framework: str = "consultative") -> dict:
    lang = language or c.get("preferred_language") or "vi"
    if lang not in ("vi", "zh", "en"):
        lang = "vi"
    bank = bank_name or BANK_NAME
    key = product
    if product == "VAY_VLD" and "VAY_VLD" in (c.get("products_held") or []):
        key = "VAY_VLD_RENEW"
    if key not in T:
        raise KeyError(product)
    tpl = T[key][lang]
    f = build_facts(c, mt, lang)
    title_zh = TITLES.get(c.get("contact_title") or "GD", TITLES["GD"])["zh"]
    title = TITLES.get(c.get("contact_title") or "GD", TITLES["GD"])[lang if lang in ("vi", "en") else "vi"]
    given = _given(c.get("contact_name") or "")
    zh_name = c.get("contact_name_zh") or (c.get("contact_name") or "")

    hook = tpl["hook"].format(**f)
    bullets = [b.format(**f) for b in tpl["bullets"]]
    ask = tpl["ask"].format(**f)
    fw = FW.get(framework, {}).get(lang)
    if fw:
        names = dict(company=c["name"], company_zh=c.get("name_zh") or c["name"])
        hook = fw["pre"].format(**names).replace("\\n", "\n") + hook
        ask = fw["post"].format(**names) + ask
    subject = tpl["subject"].format(**f)
    disc = DISCLAIMER[lang]

    if lang == "zh":
        greet = f"{zh_name}{title_zh}您好："
        sign = f"此致\n{rm_name}｜{bank}"
    elif lang == "en":
        greet = f"Dear {c.get('contact_name') or 'Sir/Madam'},"
        sign = f"Best regards,\n{rm_name} | {bank}"
    else:
        greet = f"Kính gửi Anh/Chị {given} ({title}),"
        sign = f"Trân trọng,\n{rm_name} – {bank}"

    if channel == "email":
        body = f"{greet}\n\n{hook}\n\n" + "\n".join(f"• {b}" for b in bullets) + f"\n\n{ask}\n{disc}\n\n{sign}"
    elif channel == "call":
        s = CALL[lang]
        when = {"vi": "chiều mai 14:00", "zh": "明天下午2点", "en": "tomorrow 2pm"}[lang]
        body = (f"【{s['open']}】\n" + s["open_t"].format(given=given, rm=rm_name, bank=bank, company=c["name"],
                                                       company_zh=c.get("name_zh") or c["name"], name=zh_name, title_zh=title_zh)
                + f"\n\n【{s['disc']}】\n- " + "\n- ".join(d.format(company=c["name"], company_zh=c.get("name_zh") or c["name"]) for d in s["disc_t"])
                + f"\n- ({s['hint']}) {hook}\n- {ask}"
                + f"\n\n【{s['obj']}】\n" + "\n".join(f"- {o}: {r}" for o, r in s["obj_t"])
                + f"\n\n【{s['close']}】\n" + s["close_t"].format(when=when))
        subject = None
    else:  # zalo
        short = "\n".join(f"• {b}" for b in bullets[:2])
        body = f"{greet}\n\n{hook}\n{short}\n\n{ask}\n{disc}\n{sign}"
        subject = None

    return {
        "customer_id": c["customer_id"], "product": product, "product_name": PRODUCTS[product][lang if lang in PRODUCTS[product] else "vi"],
        "channel": channel, "language": lang, "subject": subject, "body": body, "chars": len(body),
    }
