from pydantic import BaseModel
import os
import tempfile
import difflib
import re
import models
import seed

# ⭐️ Depends와 Session 추가
from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import engine, SessionLocal
from dotenv import load_dotenv
from openai import OpenAI

# DB 테이블 생성
models.Base.metadata.create_all(bind=engine)

seed.load_seed_data()

# ⭐️ DB 세션 의존성 함수 추가
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# --- 발음 평가 함수 ---
def evaluate_pronunciation(original_text: str, spoken_text: str):
    clean_original = re.sub(r'[^\w\s]', '', original_text).lower().split()
    clean_spoken = re.sub(r'[^\w\s]', '', spoken_text).lower().split()
    matcher = difflib.SequenceMatcher(None, clean_original, clean_spoken)
    
    score = int(matcher.ratio() * 100)
    feedback = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            feedback.append(f"'{' '.join(clean_original[i1:i2])}' 부분을 '{' '.join(clean_spoken[j1:j2])}'(으)로 잘못 발음했습니다.")
        elif tag == 'delete':
            feedback.append(f"'{' '.join(clean_original[i1:i2])}' 단어를 빠뜨렸습니다.")
        elif tag == 'insert':
            feedback.append(f"대본에 없는 '{' '.join(clean_spoken[j1:j2])}' 단어가 추가되었습니다.")

    return {
        "score": score,
        "feedback": feedback if feedback else ["완벽합니다! 오류가 없습니다."]
    }

# --- ⭐️ 특정 문장을 DB에서 불러오는 새로운 API ---
@app.get("/api/scripts/{script_id}")
def get_script(script_id: int, db: Session = Depends(get_db)):
    script = db.query(models.ReadingScript).filter(models.ReadingScript.id == script_id).first()
    if not script:
        return {"status": "error"}
    return {"status": "success", "id": script.id, "text": script.original_text}

# --- 메인 화면 (HTML) ---
@app.get("/")
async def main():
    content = """
    <!DOCTYPE html>
    <html>
    <head><title>발음 평가 테스트</title></head>
    <body>
        <h2>음성 녹음 및 발음 분석 테스트</h2>
        
        <!-- ⭐️ 이전/다음 문장 이동 버튼 추가 -->
        <div>
            <button id="prevBtn" disabled>이전 문장</button>
            <button id="nextBtn">다음 문장</button>
        </div>
        
        <p><strong>읽어볼 문장:</strong> <span id="targetText" style="font-size: 1.2em; font-weight: bold;">문장을 불러오는 중...</span></p>
        
        <!-- ⭐️ 새로 추가할 '듣기' 버튼 -->
        <button id="listenBtn">원어민 발음 듣기 🔊</button>

        <button id="start">녹음 시작</button>
        <button id="stop" disabled>녹음 종료 및 분석</button>
        <p id="status">대기 중...</p>
        
        <div id="resultBox" style="margin-top: 20px; padding: 10px; border: 1px solid #ccc; display: none;">
            <h3 id="growthMessage" style="color: #28a745; margin-bottom: 15px;"></h3>
            <p><strong>인식된 내 발음:</strong> <span id="recognizedText" style="color: blue;"></span></p>
            <p><strong>발음 점수:</strong> <span id="score" style="color: red; font-weight: bold;"></span>점</p>
            <p><strong>피드백:</strong></p>
            <ul id="feedbackList"></ul>
        </div>

        <script>
            let mediaRecorder;
            let audioChunks = [];
            let currentScriptId = 1; // ⭐️ 현재 읽고 있는 문장 번호 기억하기

            // ⭐️ 문장 불러오기 함수
            async function loadScript(id) {
                const response = await fetch(`/api/scripts/${id}`);
                const data = await response.json();
                
                if (data.status === 'success') {
                    currentScriptId = id;
                    document.getElementById('targetText').innerText = data.text;
                    document.getElementById('prevBtn').disabled = (id <= 1); // 1번이면 이전 버튼 비활성화
                    document.getElementById('resultBox').style.display = 'none'; // 새 문장 불러오면 결과창 숨기기
                } else {
                    alert("더 이상 문장이 없습니다!");
                }
            }

            // 페이지가 열리면 1번 문장 불러오기
            window.onload = () => loadScript(currentScriptId);

            // 버튼 클릭 이벤트 연결
            document.getElementById('prevBtn').onclick = () => loadScript(currentScriptId - 1);
            document.getElementById('nextBtn').onclick = () => loadScript(currentScriptId + 1);

            // ⭐️ 듣기 버튼 클릭 이벤트 설정
            document.getElementById('listenBtn').onclick = () => {
            // 1. 화면에 표시된 현재 문장을 가져옵니다.
            const textToSpeak = document.getElementById('targetText').innerText;
    
            // 2. 문장이 비어있지 않을 때만 실행합니다.
            if (textToSpeak && textToSpeak !== "문장을 불러오는 중...") {
            // 브라우저 내장 TTS 객체 생성
                const utterance = new SpeechSynthesisUtterance(textToSpeak);
        
                // 옵션 설정
                utterance.lang = 'en-US'; // 영어(미국) 발음으로 강제 설정
                utterance.rate = 0.9;     // 학생들이 듣고 따라하기 좋게 속도를 살짝 낮춤 (기본값: 1.0)
                utterance.pitch = 1.0;    // 음높이 (기본값: 1.0)
        
                // 재생!
                window.speechSynthesis.speak(utterance);
                }
            };

            document.getElementById('start').onclick = async () => {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                
                document.getElementById('start').disabled = true;
                document.getElementById('stop').disabled = false;
                document.getElementById('status').innerText = "마이크 녹음 중...";
                document.getElementById('resultBox').style.display = 'none';

                mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
            };

            document.getElementById('stop').onclick = async () => {
                mediaRecorder.stop();
                document.getElementById('start').disabled = false;
                document.getElementById('stop').disabled = true;
                document.getElementById('status').innerText = "Whisper API 분석 및 평가 중...";

                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    audioChunks = [];
                    
                    const formData = new FormData();
                    formData.append("file", audioBlob, "record.webm");
                    formData.append("script_id", currentScriptId); // ⭐️ 현재 문장 번호를 서버로 전송
                    // 로그인 기능이 아직 없으니 임시로 1번 학생이라고 보냅니다.
                    formData.append("student_id", 1);

                    try {
                        const response = await fetch('/analyze', { method: 'POST', body: formData });
                        const data = await response.json();
                        
                        if (data.status === 'success') {
                            document.getElementById('growthMessage').innerText = data.growth_message;
                            document.getElementById('recognizedText').innerText = data.recognized_text;
                            document.getElementById('score').innerText = data.score;
                            
                            const feedbackList = document.getElementById('feedbackList');
                            feedbackList.innerHTML = "";
                            data.feedback.forEach(item => {
                                const li = document.createElement('li');
                                li.innerText = item;
                                feedbackList.appendChild(li);
                            });
                            
                            document.getElementById('resultBox').style.display = 'block';
                            document.getElementById('status').innerText = "분석 완료!";
                        } else {
                            alert(data.message);
                            document.getElementById('status').innerText = "분석 실패";
                        }
                    } catch (error) {
                        alert("서버 통신 에러가 발생했습니다.");
                    }
                };
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=content)


# --- 분석 API ---
@app.post("/analyze")
async def analyze_audio( 
    script_id: int = Form(...),
    # ⭐️ 프론트엔드에서 학생 ID도 함께 보내준다고 가정하고 Form 데이터를 추가로 받습니다.
    # 로그인 구현 전까지는 임시로 기본값(예: 1번 학생)을 주거나, 프론트에서 임의의 숫자를 보내게 합니다.
    student_id: int = Form(1),
    file: UploadFile = File(...),
    db: Session = Depends(get_db) # ⭐️ DB 연결 다시 활성화!
):
    # ⭐️ DB에서 정답 문장 찾아오기
    script = db.query(models.ReadingScript).filter(models.ReadingScript.id == script_id).first()
    if not script:
        return {"status": "error", "message": "해당 문장을 찾을 수 없습니다."}
        
    original_text = script.original_text

    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        temp_audio.write(await file.read())
        temp_audio_path = temp_audio.name

    try:
        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",    # 👈 무조건 영어로만 듣도록 강제
                temperature=0.0   # 👈 추측해서 교정하는 기능 차단
            )
        transcript_text = transcript.text

        evaluation_result = evaluate_pronunciation(original_text, transcript_text)

        current_score = evaluation_result["score"]

        # ⭐️ 1. 새 기록을 저장하기 전에, 이 문장의 가장 최근 기록(과거 기록)을 찾아봅니다.
        previous_record = db.query(models.PronunciationHistory)\
            .filter(models.PronunciationHistory.student_id == student_id,
                    models.PronunciationHistory.script_id == script_id)\
            .order_by(models.PronunciationHistory.created_at.desc()).first()

        # ⭐️ 2. 비교 메시지 생성
        growth_message = "첫 도전이네요! 멋진 시작입니다."
        if previous_record:
            diff = current_score - previous_record.score
            if diff > 0:
                growth_message = f"🎉 지난번({previous_record.score}점)보다 {diff}점 올랐어요! 훌륭합니다!"
            elif diff < 0:
                growth_message = f"💪 지난번 최고점은 {previous_record.score}점이었어요. 조금만 더 연습해 볼까요?"
            else:
                growth_message = "✨ 지난번과 점수가 같아요. 꾸준한 실력이네요!"

        # ⭐️ 3. 새로운 기록 DB에 저장
        history_record = models.PronunciationHistory(
            student_id=student_id,
            script_id=script_id,
            recognized_text=transcript_text,
            score=current_score
        )
        db.add(history_record)
        db.commit()

        return {
            "status": "success",
            "original_text": original_text,
            "recognized_text": transcript_text,
            "score": evaluation_result["score"],
            "feedback": evaluation_result["feedback"],
            "growth_message": growth_message  # 👈 프론트엔드로 메시지 전달!
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"분석 실패: {str(e)}"
        }
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

# 프론트엔드에서 백엔드로 보낼 데이터 형식 정의
class AlimtalkRequest(BaseModel):
    student_name: str
    egi_score: float
    phone_number: str

# 강사용 페이지에서 호출할 알림톡 발송 API
@app.post("/api/admin/send-alimtalk")
def send_mock_alimtalk(request: AlimtalkRequest):
    # 실제 카카오 서버로 보내는 대신, 터미널(콘솔) 창에 예쁘게 결과를 출력해 줌
    print("\n" + "="*50)
    print("📲 [카카오톡 알림톡 자동 발송 시스템 - MOCK]")
    print(f"➡️ 수신자 번호: {request.phone_number}")
    print(f"➡️ 메시지 내용:")
    print(f"   [방과후 영어교실]")
    print(f"   학부모님, {request.student_name} 학생의 월간 성장리포트가 도착했습니다.")
    print(f"   이번 달 영어 성장지수(EGI)는 {request.egi_score}점입니다.")
    print("="*50 + "\n")
    
    # 프론트엔드에게는 "발송 성공"이라고 거짓말(Mocking)을 해줌
    return {
        "status": "success", 
        "message": f"{request.student_name} 학생의 알림톡 발송 성공 (시뮬레이션)"
    }
