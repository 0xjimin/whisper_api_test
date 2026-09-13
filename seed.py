import json
import models
from database import engine, SessionLocal

# DB 테이블 생성
models.Base.metadata.create_all(bind=engine)

def load_seed_data():
    db = SessionLocal()
    # DB가 비어있는지 확인
    if db.query(models.ReadingScript).count() == 0:
        # JSON 파일 읽어오기
        with open("scripts.json", "r", encoding="utf-8") as f:
            scripts_data = json.load(f)
            
            # 읽어온 데이터를 DB에 하나씩 추가
            for item in scripts_data:
                new_script = models.ReadingScript(
                    level=item["level"], 
                    original_text=item["original_text"]
                )
                db.add(new_script)
            
        db.commit()
        print("✅ 초기 문장 데이터가 DB에 성공적으로 저장되었습니다!")
    else:
        print("이미 데이터가 존재합니다.")
    db.close()

if __name__ == "__main__":
    load_seed_data()