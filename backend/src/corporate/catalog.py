"""Product catalog, stages and lookup tables for the corporate edition."""

PRODUCTS = {
    "VAY_VLD":   {"vi": "Vay vốn lưu động",                         "en": "Working capital loan",          "zh": "流动资金贷款"},
    "VAY_DT":    {"vi": "Vay đầu tư / tài trợ dự án",               "en": "Investment / project finance",  "zh": "投资/项目融资"},
    "LC":        {"vi": "Thư tín dụng (L/C) nhập khẩu",             "en": "Import L/C",                    "zh": "进口信用证"},
    "UPAS":      {"vi": "UPAS L/C (tài trợ nhập khẩu trả chậm)",    "en": "UPAS L/C",                      "zh": "UPAS远期信用证融资"},
    "BAO_LANH":  {"vi": "Bảo lãnh ngân hàng",                       "en": "Bank guarantee",                "zh": "银行保函"},
    "TTQT":      {"vi": "Thanh toán quốc tế (T/T, nhờ thu)",        "en": "International payments",        "zh": "国际结算"},
    "NGOAI_TE":  {"vi": "Mua bán ngoại tệ & phòng ngừa tỷ giá",     "en": "FX & hedging",                  "zh": "外汇买卖及汇率避险"},
    "LUONG":     {"vi": "Chi lương & thẻ cho người lao động",       "en": "Payroll & cards",               "zh": "代发工资及员工卡"},
    "DONG_TIEN": {"vi": "Quản lý dòng tiền (thu hộ/chi hộ, iBanking DN)", "en": "Cash management",         "zh": "现金管理"},
    "TIEN_GUI":  {"vi": "Tiền gửi có kỳ hạn",                       "en": "Term deposit",                  "zh": "定期存款"},
}

STAGES = ["Tiếp cận", "Đang tư vấn", "Thẩm định", "Trình duyệt", "Triển khai", "Thất bại"]
STAGE_PROB = {"Tiếp cận": 15, "Đang tư vấn": 30, "Thẩm định": 50, "Trình duyệt": 70, "Triển khai": 90, "Thất bại": 0}

INDUSTRIES = {
    "Dệt may – Da giày":          {"short": "Dệt May",   "export": (0.5, 0.9), "import": (0.3, 0.6), "emp_per_bn": 6.0},
    "Điện tử – Linh kiện":        {"short": "Điện tử",   "export": (0.4, 0.9), "import": (0.4, 0.8), "emp_per_bn": 3.0},
    "Cơ khí chế tạo":             {"short": "Cơ khí",    "export": (0.1, 0.5), "import": (0.2, 0.5), "emp_per_bn": 2.5},
    "Nhựa – Bao bì":              {"short": "Nhựa",      "export": (0.1, 0.4), "import": (0.3, 0.6), "emp_per_bn": 2.5},
    "Thực phẩm – Đồ uống":        {"short": "Thực phẩm", "export": (0.0, 0.3), "import": (0.1, 0.3), "emp_per_bn": 2.0},
    "Gỗ – Nội thất":              {"short": "Gỗ",        "export": (0.5, 0.9), "import": (0.2, 0.4), "emp_per_bn": 4.0},
    "Logistics – Vận tải":        {"short": "Vận tải",   "export": (0.0, 0.1), "import": (0.0, 0.2), "emp_per_bn": 2.0},
    "Xây dựng – Hạ tầng":         {"short": "Xây dựng",  "export": (0.0, 0.05), "import": (0.05, 0.2), "emp_per_bn": 3.0},
    "Thương mại XNK":             {"short": "Thương mại", "export": (0.1, 0.5), "import": (0.4, 0.8), "emp_per_bn": 0.6},
    "Hóa chất – Phân bón":        {"short": "Hóa chất",  "export": (0.1, 0.4), "import": (0.4, 0.7), "emp_per_bn": 1.0},
    "Nông sản – Thủy sản":        {"short": "Nông sản",  "export": (0.4, 0.9), "import": (0.05, 0.2), "emp_per_bn": 3.5},
    "Vật liệu xây dựng":          {"short": "Vật liệu",  "export": (0.0, 0.3), "import": (0.1, 0.3), "emp_per_bn": 1.5},
    "Năng lượng tái tạo":         {"short": "Năng lượng", "export": (0.0, 0.0), "import": (0.2, 0.5), "emp_per_bn": 0.4},
    "Phát triển hạ tầng KCN":     {"short": "Phát triển KCN", "export": (0.0, 0.0), "import": (0.0, 0.1), "emp_per_bn": 0.5},
}
GUARANTEE_INDUSTRIES = {"Xây dựng – Hạ tầng", "Logistics – Vận tải", "Cơ khí chế tạo", "Năng lượng tái tạo", "Phát triển hạ tầng KCN", "Vật liệu xây dựng"}
CAPEX_INDUSTRIES = {"Phát triển hạ tầng KCN", "Năng lượng tái tạo", "Điện tử – Linh kiện", "Cơ khí chế tạo"}

# (province, [industrial zones], weight)
LOCATIONS = [
    ("TP. Hồ Chí Minh", ["KCN Hiệp Phước", "KCX Tân Thuận", "KCN Vĩnh Lộc", "KCN Tân Bình", "KCX Linh Trung"], 22),
    ("Bình Dương", ["VSIP 1", "VSIP 2", "KCN Mỹ Phước 3", "KCN Sóng Thần", "KCN Việt Hương"], 22),
    ("Đồng Nai", ["KCN Biên Hòa 2", "KCN Amata", "KCN Long Thành", "KCN Nhơn Trạch", "KCN Hố Nai"], 18),
    ("Long An", ["KCN Đức Hòa 1", "KCN Hải Sơn", "KCN Long Hậu", "KCN Tân Đức"], 11),
    ("Bà Rịa – Vũng Tàu", ["KCN Phú Mỹ 1", "KCN Mỹ Xuân A2", "KCN Đông Xuyên"], 6),
    ("Bắc Ninh", ["KCN Yên Phong", "KCN Quế Võ"], 7),
    ("Hải Phòng", ["KCN Đình Vũ", "KCN Tràng Duệ"], 6),
    ("Hưng Yên", ["KCN Phố Nối A"], 3),
    ("Tây Ninh", ["KCN Trảng Bàng", "KCN Phước Đông"], 5),
]

FDI_COUNTRIES = [("Trung Quốc", 40), ("Đài Loan", 25), ("Hàn Quốc", 14), ("Nhật Bản", 14), ("Singapore", 7)]
TITLES = {
    "GD":  {"vi": "Giám đốc",           "zh": "总经理",   "en": "General Director"},
    "PGD": {"vi": "Phó Giám đốc",       "zh": "副总经理", "en": "Deputy Director"},
    "KTT": {"vi": "Kế toán trưởng",     "zh": "财务经理", "en": "Chief Accountant"},
    "CFO": {"vi": "Giám đốc Tài chính", "zh": "财务总监", "en": "CFO"},
}
LANG_NAMES = {"vi": "Tiếng Việt", "zh": "中文", "en": "English"}


# Loại khách: KH mới/tiềm năng (đang theo dõi bán hàng) vs KH hiện hữu TPBank
LIFECYCLES = {"prospect": "KH mới (tiềm năng)", "existing": "Hiện hữu TPBank"}
