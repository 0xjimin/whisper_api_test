from sqlalchemy import Column, Integer, String
from database import Base

# models.py 파일 내에 아래 코드를 추가합니다.
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.sql import func
# 기존에 정의된 Base가 있다면 그것을 사용하세요. (예: from database import Base)

class PronunciationHistory(Base):
    __tablename__ = "pronunciation_histories"

    id = Column(Integer, primary_key=True, index=True)
    # 1번 질문이었던 로그인 기능이 완성되면 사용될 학생 고유 ID입니다.
    student_id = Column(Integer, index=True) 
    # 어떤 문장을 읽었는지 (현재 main.py에 있는 models.ReadingScript의 id와 연결됩니다)
    script_id = Column(Integer, index=True)
    
    # 기록용 데이터
    recognized_text = Column(String) # 학생이 실제로 말한(인식된) 문장
    score = Column(Integer)          # 발음 점수
    
    # 기록된 날짜 및 시간 (자동 생성)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ReadingScript(Base):
    __tablename__ = "reading_scripts"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(Integer)
    original_text = Column(String)