import os
from datetime import datetime
from google import genai
from flask import jsonify
from google.genai import types
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from authlib.integrations.flask_client import OAuth
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from dotenv import load_dotenv
from supabase import create_client

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ai_client = None

if GEMINI_API_KEY:
    # 2026년 표준 최신 google-genai SDK 클라이언트 초기화 방식
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    print("경고: GEMINI_API_KEY가 설정되지 않았습니다. 챗봇 기능이 작동하지 않습니다.")

# =========================
# 환경변수 로드
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(BASE_DIR, ".env")

load_dotenv(dotenv_path)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "my_secret_key")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

print(f"supabase_url: {SUPABASE_URL}")

# =========================
# Flask 설정
# =========================

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# =========================
# Supabase 연결
# =========================

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

oauth = OAuth(app)
google_oauth = None

if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
    google_oauth = oauth.register(
        name="google",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"}
    )


def get_current_temperature():
    """
    Supabase DB의 'sensor_data' 테이블에서 가장 최근에 측정된 현재 온도 데이터를 조회합니다.
    """
    try:

        response = (
            supabase.table("sensor_data")
            .select("temperature")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return {"temperature": response.data[0]["temperature"]}
    except Exception as e:
        return {"error": f"DB 조회 중 오류 발생: {str(e)}"}

def get_next_user_id():

    max_id_response = (
        supabase.table("users")
        .select("userId")
        .order("userId", desc=True)
        .limit(1)
        .execute()
    )

    if max_id_response.data:
        return int(max_id_response.data[0]["userId"]) + 1

    return 1


def set_login_session(user):

    session["logged_in"] = True
    session["user_id"] = user["userId"]
    session["user_name"] = user["userName"]
    session["user_account_id"] = user["userAccountId"]


def get_or_create_google_user(user_info):

    account_id = user_info.get("email") or f"google:{user_info.get('sub')}"
    display_name = user_info.get("name") or user_info.get("given_name") or account_id

    existing_user = (
        supabase.table("users")
        .select("*")
        .eq("userAccountId", account_id)
        .limit(1)
        .execute()
    )

    if existing_user.data:
        return existing_user.data[0]

    result = (
        supabase.table("users")
        .insert(
            {
                "userId": get_next_user_id(),
                "userAccountId": account_id,
                "userPassword": None,
                "userName": display_name,
                "userPhoneNumber": None,
                "userPaymentStatus": "unpaid",
                "userCreateDate": datetime.now().isoformat(),
                "userActiveStatus": "active"
            }
        )
        .execute()
    )

    if result.data:
        return result.data[0]

    fallback_user = (
        supabase.table("users")
        .select("*")
        .eq("userAccountId", account_id)
        .limit(1)
        .execute()
    )

    if fallback_user.data:
        return fallback_user.data[0]

    raise RuntimeError("구글 계정 사용자 생성에 실패했습니다.")

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

            if not user.get("userPassword"):

                flash("이 계정은 구글 로그인으로 이용해 주세요.")
                return redirect(url_for("login"))

            if not check_password_hash(
                user["userPassword"],
                password
            ):
                flash("비밀번호가 틀렸습니다.")
                return redirect(url_for("login"))

            set_login_session(user)

            flash("로그인 성공")

            return redirect(url_for("board"))

        except Exception as e:

            print("로그인 오류")
            print(e)

            flash(str(e))

            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/login/google")
def login_google():

    if not google_oauth:

        flash("구글 로그인 설정이 완료되지 않았습니다.")
        return redirect(url_for("login"))

    redirect_uri = GOOGLE_REDIRECT_URI or url_for("login_google_callback", _external=True)

    return google_oauth.authorize_redirect(redirect_uri)


@app.route("/auth/google/callback")
def login_google_callback():
    if not google_oauth:
        flash("구글 로그인 설정이 완료되지 않았습니다.")
        return redirect(url_for("login"))

    try:
        # 1. 구글로부터 액세스 토큰 수신
        token = google_oauth.authorize_access_token()
        
        # 2. 토큰 내에 userinfo 데이터가 포함되어 있는지 우선 확인 (가장 안전함)
        user_info = token.get('userinfo')
        
        # 3. 만약 없다면 id_token 파싱 시도 후, 그것도 없으면 API 직접 호출
        if not user_info:
            try:
                user_info = google_oauth.parse_id_token(token)
            except Exception:
                user_info = google_oauth.get("https://www.googleapis.com/oauth2/v3/userinfo").json()

        # 데이터가 정상적으로 수신되었는지 터미널에서 확인용 프린트
        print("구글에서 받아온 유저 정보:", user_info)

        if not user_info:
            raise ValueError("구글 유저 정보를 가져오지 못했습니다.")

        # 4. Supabase DB 연동 및 세션 세팅
        user = get_or_create_google_user(user_info)
        set_login_session(user)

        flash("구글 로그인 성공")
        return redirect(url_for("board"))

    except Exception as e:
        print("구글 로그인 상세 오류 발생:")
        import traceback
        traceback.print_exc()  # 터미널에 에러가 몇 번째 줄에서 왜 났는지 명확하게 찍어줍니다.

        flash("구글 로그인에 실패했습니다.")
        return redirect(url_for("login"))
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

            result = (
                supabase.table("users")
                .insert(
                    {
                        "userId": get_next_user_id(),
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
# 챗봇 API 엔드포인트
# =========================
@app.route("/api/chatbot", methods=["POST"])
def chatbot_api():
    # 1. 로그인 여부 및 세션 검증
    if not session.get("logged_in"):
        return jsonify({"error": "로그인이 필요합니다."}), 401

    if not ai_client:
        return jsonify({"error": "AI 서비스 서버 설정이 되어있지 않습니다."}), 500

    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "메시지가 비어있습니다."}), 400

    current_user_id = session.get("user_id")
    current_user_name = session.get("user_name")
    
    # AI에게 기본적으로 전달할 시스템 지침
    system_instruction = (
        f"당신은 IoT 모니터링 시스템의 친절한 AI 게시판 도우미입니다. "
        f"답변을 받는 유저의 이름은 '{current_user_name}'님(User ID: {current_user_id})입니다. "
        f"제공된 데이터가 있다면 기반으로 설명하고, 데이터가 없다면 일반적인 답변을 해주세요."
    )

    db_context = ""

    try:
        # 2. 유저가 센서나 장비 데이터를 요구하는지 키워드 체크
        if any(keyword in user_message for keyword in ["센서", "온도", "값", "데이터", "수치", "sensor"]):
            
            # 숫자(센서 ID) 추출 시도 (예: "1번 센서" -> 1)
            import re
            sensor_ids = re.findall(r'\d+', user_message)
            
            if sensor_ids:
                target_sensor_id = int(sensor_ids[0])
                
                # [Supabase 조회] 실제 제공된 테이블 구조 반영: sensorvalue와 sensor 테이블 정보 결합
                # sensorId가 일치하는 가장 최신(sensorvaluetime 기준 내림차순) 데이터 1건 조회
                db_response = (
                    supabase.table("sensorvalue")
                    .select("sensorValue, sensorvaluetime, sensor(sensorType, sensorModelName)")
                    .eq("sensorId", target_sensor_id)
                    .order("sensorvaluetime", desc=True)
                    .limit(1)
                    .execute()
                )
                
                if db_response.data:
                    latest_data = db_response.data[0]
                    val = latest_data.get("sensorValue")
                    v_time = latest_data.get("sensorvaluetime")
                    s_info = latest_data.get("sensor", {})
                    s_type = s_info.get("sensorType", "알 수 없음")
                    s_model = s_info.get("sensorModelName", "알 수 없음")
                    
                    # AI에게 넘겨줄 실시간 컨텍스트 데이터 조립
                    db_context = (
                        f"\n[실시간 DB 조회 정보]\n"
                        f"- 요청된 센서 ID: {target_sensor_id}\n"
                        f"- 센서 모델 및 타입: {s_model} ({s_type})\n"
                        f"- 가장 최근 측정 값: {val}\n"
                        f"- 측정 시간: {v_time}\n"
                    )
                else:
                    db_context = f"\n[알림] DB의 'sensorvalue' 테이블에서 센서 ID {target_sensor_id}번에 대한 측정 데이터를 찾을 수 없습니다."
            
            else:
                # 특정 센서 번호 지정을 안 하고 "센서 값 보여줘"라고 한 경우 전체 요약 시도
                db_response = (
                    supabase.table("sensorvalue")
                    .select("sensorId, sensorValue, sensorvaluetime")
                    .order("sensorvaluetime", desc=True)
                    .limit(3)
                    .execute()
                )
                if db_response.data:
                    db_context = "\n[최신 등록된 센서 데이터 현황]\n"
                    for row in db_response.data:
                        db_context += f"- 센서 {row['sensorId']}번: 값 {row['sensorValue']} (측정일시: {row['sensorvaluetime']})\n"

        # 3. Gemini API 호출 (DB 콘텍스트가 있다면 프롬프트에 병합)
        final_prompt = user_message
        if db_context:
            final_prompt = f"{db_context}\n\n유저의 질문: {user_message}\n\n위의 [실시간 DB 조회 정보]를 참고하여 유저에게 상황을 친절하게 설명해 주세요."

        # 2026년 표준 google-genai SDK 양식으로 호출
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=final_prompt,
            config={
                'system_instruction': system_instruction,
                'temperature': 0.5 # 데이터 기반 답변이므로 정확도를 위해 약간 낮춤
            }
        )
        
        ai_reply = response.text
        return jsonify({"reply": ai_reply})

    except Exception as e:
        print(f"챗봇 엔드포인트 에러 발생: {e}")
        # 에러 발생 시 유저가 화면에서 파악할 수 있도록 구체적인 실패 사유 반환
        return jsonify({"reply": f"죄송합니다, {current_user_name}님. 데이터를 조회하거나 AI 답변을 생성하는 중 오류가 발생했습니다. (오류 내용: {str(e)})"}), 200

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
