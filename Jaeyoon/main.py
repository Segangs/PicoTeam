from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from supabase import create_client, Client
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Supabase 연결 설정 (프로젝트 설정에서 URL과 API 키를 가져와 여기에 입력하세요)
SUPABASE_URL = "https://YOUR_SUPABASE_HOST_PLACEHOLDER"
SUPABASE_KEY = "YOUR_SUPABASE_ANON_KEY_PLACEHOLDER"

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Supabase 연결 오류: {e}")
    supabase = None

@app.route('/')
def index():
    if 'user_id' in session:
        return f"Welcome, {session.get('user_name')}! <a href='/logout'>Logout</a>"
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        account_id = request.form.get('userAccountId')
        password = request.form.get('userPassword')

        if supabase:
            try:
                # Supabase의 특정 조건 조회 명령어 (.eq 메서드 체이닝) - 아이디로만 먼저 조회
                response = supabase.table('users') \
                    .select('*') \
                    .eq('userAccountId', account_id) \
                    .execute()
                
                # 데이터가 존재하고, 비밀번호 해시가 일치하면(로그인 성공)
                if response.data and len(response.data) > 0:
                    user = response.data[0]
                    stored_password_hash = user.get('userPassword', user.get('userpassword'))
                    
                    if stored_password_hash and check_password_hash(stored_password_hash, password):
                        # PostgREST(Supabase API)는 DB 설정에 따라 소문자 키로 반환할 수도 있습니다.
                        session['user_id'] = user.get('userId', user.get('userid'))
                        session['user_name'] = user.get('userName', user.get('username'))
                        return redirect(url_for('index'))
                    else:
                        flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
                else:
                    flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
            except Exception as e:
                flash(f'데이터베이스 조회 중 오류가 발생했습니다: {e}', 'error')
        else:
            flash('Supabase에 연결되어 있지 않습니다.', 'error')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        account_id = request.form.get('userAccountId')
        password = request.form.get('userPassword')
        name = request.form.get('userName')
        phone = request.form.get('userPhoneNumber')

        if supabase:
            try:
                # 1. 이미 존재하는 아이디인지 확인
                existing = supabase.table('users').select('userId').eq('userAccountId', account_id).execute()
                if existing.data and len(existing.data) > 0:
                    flash('이미 존재하는 아이디입니다.', 'error')
                    return redirect(url_for('register'))
                
                # 2. 가장 높은 userId 값 찾기 (PostgreSQL의 Auto-increment/Serial이라면 원래 안해도 되지만 스키마에 맞춰 유지)
                max_id_response = supabase.table('users').select('userId').order('userId', desc=True).limit(1).execute()
                new_user_id = 1
                if max_id_response.data and len(max_id_response.data) > 0:
                    current_max = max_id_response.data[0].get('userId', max_id_response.data[0].get('userid'))
                    new_user_id = int(current_max) + 1

                # 비밀번호 암호화 (해싱)
                hashed_password = generate_password_hash(password)

                # 3. 새로운 사용자 삽입 (Supabase insert 명령어)
                new_user_data = {
                    "userId": new_user_id,
                    "userAccountId": account_id,
                    "userPassword": hashed_password,
                    "userName": name,
                    "userPhoneNumber": phone,
                    "userCreateDate": datetime.now().isoformat(),
                    "userActiveStatus": 'ACTIVE'
                }
                
                supabase.table('users').insert(new_user_data).execute()
                flash('회원가입이 완료되었습니다! 로그인해주세요.', 'success')
                return redirect(url_for('login'))
                
            except Exception as e:
                flash(f'회원가입 중 오류가 발생했습니다: {e}', 'error')
        else:
            flash('Supabase에 연결되어 있지 않습니다.', 'error')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
