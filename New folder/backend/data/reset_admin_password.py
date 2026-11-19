"""Đặt lại mật khẩu một tài khoản (dùng khi quên mật khẩu Admin cuối cùng).

Trên VPS Docker:   docker compose exec -it api python data/reset_admin_password.py <tên_đăng_nhập>
Trên máy Windows:  backend\\.venv\\Scripts\\python data\\reset_admin_password.py <tên_đăng_nhập>
Cần quyền truy cập máy chủ — đó chính là lớp bảo vệ của lệnh này. Mọi phiên đăng nhập cũ của tài khoản bị hủy.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import SessionLocal, init_db  # noqa: E402
from src.accounts.models import AppUser  # noqa: E402
from src.accounts import service as S  # noqa: E402


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    username = argv[1].strip().lower()
    pw = os.environ.get("NEW_PASSWORD") or getpass.getpass("Mật khẩu mới: ")
    if not os.environ.get("NEW_PASSWORD") and getpass.getpass("Nhập lại: ") != pw:
        print("Hai lần nhập không khớp.")
        return 1
    err = S.check_password_policy(pw)
    if err:
        print(err)
        return 1
    init_db()
    db = SessionLocal()
    try:
        u = db.query(AppUser).filter_by(username=username).first()
        if not u:
            names = ", ".join(x.username for x in db.query(AppUser).all()) or "(chưa có tài khoản nào)"
            print(f"Không có tài khoản '{username}'. Hiện có: {names}")
            return 1
        u.password_hash = S.hash_password(pw)
        u.is_active = True
        u.must_change_password = False
        S.revoke_user_sessions(db, u.id)
        db.commit()
        S.audit(S._to_auth(u), "password.reset.cli", "user", u.id, "đặt lại bằng dòng lệnh trên máy chủ")
        print(f"Đã đặt lại mật khẩu cho '{username}' (tài khoản được mở khóa nếu đang bị khóa). Nếu vừa nhập sai nhiều lần, chờ 5 phút hoặc khởi động lại: docker compose restart api")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
