import os
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from dotenv import load_dotenv
from supabase import create_client

# =========================
# 환경변수 로드
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")

load_dotenv(dotenv_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print(f"supabase_url: {SUPABASE_URL}")

# =========================
# Flask 설정
# =========================

app = Flask(__name__)
app.secret_key = "my_secret_key"

# =========================
# Supabase 연결
# =========================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

# =========================
# 메인
# =========================

@app.route("/")
def home():

    if session.get("logged_in"):
        return redirect(url_for("board"))

    return redirect(url_for("login"))

# =========================
# 로그인
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        account_id = request.form.get("userAccountId")
        password = request.form.get("password")

        try:

            response = (
                supabase.table("users")
                .select("*")
                .eq("userAccountId", account_id)
                .execute()
            )

            print("조회 결과:", response.data)

            if len(response.data) == 0:

                flash("존재하지 않는 아이디입니다.")
                return redirect(url_for("login"))

            user = response.data[0]

            if not check_password_hash(
                user["userPassword"],
                password
            ):
                flash("비밀번호가 틀렸습니다.")
                return redirect(url_for("login"))

            session["logged_in"] = True
            session["user_id"] = user["userId"]
            session["user_name"] = user["userName"]
            session["user_account_id"] = user["userAccountId"]

            flash("로그인 성공")

            return redirect(url_for("board"))

        except Exception as e:

            print("로그인 오류")
            print(e)

            flash(str(e))

            return redirect(url_for("login"))

    return render_template("login.html")

# =========================
# 회원가입
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        account_id = request.form.get("userAccountId")
        name = request.form.get("userName")
        phone = request.form.get("userPhoneNumber")

        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        if password != password_confirm:

            flash("비밀번호가 다릅니다.")
            return redirect(url_for("register"))

        try:

            duplicate = (
                supabase.table("users")
                .select("userId")
                .eq("userAccountId", account_id)
                .execute()
            )

            if duplicate.data:

                flash("이미 존재하는 아이디입니다.")
                return redirect(url_for("register"))

            max_id_response = (
                supabase.table("users")
                .select("userId")
                .order("userId", desc=True)
                .limit(1)
                .execute()
            )

            new_user_id = 1

            if max_id_response.data:

                new_user_id = int(max_id_response.data[0]["userId"]) + 1

            result = (
                supabase.table("users")
                .insert(
                    {
                        "userId": new_user_id,
                        "userAccountId": account_id,
                        "userPassword": generate_password_hash(password),
                        "userName": name,
                        "userPhoneNumber": phone,
                        "userPaymentStatus": "unpaid",
                        "userCreateDate": datetime.now().isoformat(),
                        "userActiveStatus": "active"
                    }
                )
                .execute()
            )

            print("회원가입 결과")
            print(result)

            flash("회원가입 성공")
            return redirect(url_for("login"))

        except Exception as e:

            print("회원가입 오류")
            print(e)

            flash(str(e))
            return redirect(url_for("register"))

    return render_template("register.html")

# =========================
# 게시판
# =========================

@app.route("/board")
def board():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:

        boards = (
            supabase.table("board")
            .select("*")
            .order("boardId")
            .execute()
        )

        return render_template(
            "board.html",
            boards=boards.data,
            user_name=session.get("user_name")
        )

    except Exception as e:

        print(e)

        return render_template(
            "board.html",
            boards=[],
            user_name=session.get("user_name")
        )

# =========================
# 게시글 작성
# =========================

def format_created_at(value):

    if not value:
        return ""

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


@app.route("/board/<int:board_id>")
def board_detail(board_id):

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    try:

        board_response = (
            supabase.table("board")
            .select("*")
            .eq("boardId", board_id)
            .limit(1)
            .execute()
        )

        if not board_response.data:
            flash("게시글을 찾을 수 없습니다.")
            return redirect(url_for("board"))

        board_item = board_response.data[0]
        author_name = "알 수 없음"

        if board_item.get("userId"):
            user_response = (
                supabase.table("users")
                .select("userName")
                .eq("userId", board_item["userId"])
                .limit(1)
                .execute()
            )

            if user_response.data:
                author_name = user_response.data[0].get("userName", author_name)

        return render_template(
            "board_detail.html",
            board=board_item,
            author_name=author_name,
            created_at=format_created_at(board_item.get("created_at")),
            user_name=session.get("user_name")
        )

    except Exception as e:

        print(e)
        flash(str(e))
        return redirect(url_for("board"))


@app.route("/write", methods=["POST"])
def write():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    title = request.form.get("title")
    content = request.form.get("content")

    try:

        supabase.table("board").insert(
            {
                "title": title,
                "content": content,
                "userId": session["user_id"],
                "created_at": datetime.now().isoformat()
            }
        ).execute()

        flash("게시글 등록 완료")

    except Exception as e:

        print(e)
        flash(str(e))

    return redirect(url_for("board"))

# =========================
# 로그아웃
# =========================

@app.route("/logout")
def logout():

    session.clear()

    flash("로그아웃 되었습니다.")

    return redirect(url_for("login"))

# =========================
# 실행
# =========================

if __name__ == "__main__":

    print("=================================")
    print("SUPABASE_URL =", SUPABASE_URL)
    print("SUPABASE 연결 성공")
    print("=================================")

    app.run(
        host="127.0.0.1",
        port=8080,
        debug=True
    )
