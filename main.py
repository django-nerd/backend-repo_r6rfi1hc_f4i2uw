import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db

app = FastAPI(title="Solo Leveling Fitness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Helpers ----------

def today_str() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def next_level_exp(level: int) -> int:
    # Progression: 100 * level^1.5
    return int(100 * (level ** 1.5))


# ---------- Models (request/response) ----------
class CreateHunterRequest(BaseModel):
    name: str
    title: Optional[str] = None


class LogWorkoutRequest(BaseModel):
    user_id: str
    workout_type: str
    minutes: int
    difficulty: str = "normal"  # easy | normal | hard


class CompleteQuestRequest(BaseModel):
    user_id: str
    date: Optional[str] = None  # default today


# ---------- Routes ----------
@app.get("/")
def root():
    return {"message": "Solo Leveling Fitness API running"}


@app.get("/test")
def test_database():
    resp = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            resp["database"] = "✅ Available"
            resp["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            resp["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
            resp["connection_status"] = "Connected"
            try:
                resp["collections"] = db.list_collection_names()[:10]
                resp["database"] = "✅ Connected & Working"
            except Exception as e:
                resp["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
    except Exception as e:
        resp["database"] = f"❌ Error: {str(e)[:80]}"
    return resp


@app.post("/api/hunters")
def create_hunter(payload: CreateHunterRequest):
    if db is None:
        raise HTTPException(500, "Database not configured")
    # Initialize a new hunter
    hunter = {
        "name": payload.name,
        "title": payload.title,
        "level": 1,
        "exp": 0,
        "streak": 0,
        "last_checkin": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    inserted_id = db["hunter"].insert_one(hunter).inserted_id
    hunter["id"] = str(inserted_id)
    return hunter


@app.get("/api/hunters")
def list_hunters():
    if db is None:
        raise HTTPException(500, "Database not configured")
    docs = db["hunter"].find({}).limit(100)
    result = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        result.append(d)
    return result


@app.post("/api/checkin")
def daily_checkin(user_id: str):
    if db is None:
        raise HTTPException(500, "Database not configured")

    try:
        hunter = db["hunter"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(400, "Invalid user id")

    if not hunter:
        raise HTTPException(404, "Hunter not found")

    today = today_str()
    last_checkin = hunter.get("last_checkin")
    last_date = last_checkin.date().isoformat() if last_checkin else None

    if last_date == today:
        return {
            "message": "Already checked in today",
            "streak": hunter.get("streak", 0),
            "level": hunter.get("level", 1),
            "exp": hunter.get("exp", 0),
        }

    # Determine streak
    new_streak = 1
    if last_checkin:
        if (datetime.now(timezone.utc).date() - last_checkin.date()).days == 1:
            new_streak = hunter.get("streak", 0) + 1

    # Award EXP for check-in
    exp_gain = 10 + min(new_streak, 20)  # small bonus scaling with streak
    new_exp = hunter.get("exp", 0) + exp_gain
    level = hunter.get("level", 1)

    # Level up loop
    leveled_up = False
    while new_exp >= next_level_exp(level):
        new_exp -= next_level_exp(level)
        level += 1
        leveled_up = True

    db["hunter"].update_one(
        {"_id": hunter["_id"]},
        {
            "$set": {
                "exp": new_exp,
                "level": level,
                "last_checkin": datetime.now(timezone.utc),
                "streak": new_streak,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # Record checkin
    db["checkin"].insert_one({
        "user_id": user_id,
        "date": today,
        "streak_after": new_streak,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    return {
        "message": "Check-in complete",
        "exp_gain": exp_gain,
        "streak": new_streak,
        "level": level,
        "exp": new_exp,
        "leveled_up": leveled_up,
    }


@app.post("/api/workouts")
def log_workout(payload: LogWorkoutRequest):
    if db is None:
        raise HTTPException(500, "Database not configured")

    # Simple EXP calculation
    diff_mult = {"easy": 1.0, "normal": 1.5, "hard": 2.0}.get(payload.difficulty, 1.5)
    exp_gain = int(payload.minutes * diff_mult)

    try:
        hunter = db["hunter"].find_one({"_id": ObjectId(payload.user_id)})
    except Exception:
        raise HTTPException(400, "Invalid user id")
    if not hunter:
        raise HTTPException(404, "Hunter not found")

    new_exp = hunter.get("exp", 0) + exp_gain
    level = hunter.get("level", 1)
    leveled_up = False
    while new_exp >= next_level_exp(level):
        new_exp -= next_level_exp(level)
        level += 1
        leveled_up = True

    db["hunter"].update_one(
        {"_id": hunter["_id"]},
        {"$set": {"exp": new_exp, "level": level, "updated_at": datetime.now(timezone.utc)}},
    )

    # Record workout
    db["workout"].insert_one({
        "user_id": payload.user_id,
        "workout_type": payload.workout_type,
        "minutes": payload.minutes,
        "difficulty": payload.difficulty,
        "exp_awarded": exp_gain,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    return {
        "message": "Workout logged",
        "exp_gain": exp_gain,
        "level": level,
        "exp": new_exp,
        "leveled_up": leveled_up,
    }


@app.get("/api/quests")
def get_daily_quests(user_id: str):
    if db is None:
        raise HTTPException(500, "Database not configured")

    try:
        user = db["hunter"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(400, "Invalid user id")
    if not user:
        raise HTTPException(404, "Hunter not found")

    today = today_str()
    quest = db["quest"].find_one({"user_id": user_id, "date": today})
    if not quest:
        # Generate default Solo Leveling style daily quests
        base = [
            ("Do 100 Push-ups", 75),
            ("Run 3 km", 90),
            ("Stretch for 10 minutes", 40),
            ("Hold a 2-minute plank", 60),
        ]
        import random
        title, reward = random.choice(base)
        quest = {
            "user_id": user_id,
            "date": today,
            "title": title,
            "description": "Complete the task to earn EXP and keep your streak.",
            "exp_reward": reward,
            "completed": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        db["quest"].insert_one(quest)

    quest_out = {**quest}
    if "_id" in quest_out:
        quest_out["id"] = str(quest_out.pop("_id"))
    return quest_out


@app.post("/api/quests/complete")
def complete_quest(payload: CompleteQuestRequest):
    if db is None:
        raise HTTPException(500, "Database not configured")

    today = payload.date or today_str()
    quest = db["quest"].find_one({"user_id": payload.user_id, "date": today})
    if not quest:
        raise HTTPException(404, "Quest not found for today")
    if quest.get("completed"):
        return {"message": "Quest already completed", "reward": quest.get("exp_reward", 0)}

    # Update quest
    db["quest"].update_one(
        {"_id": quest["_id"]},
        {"$set": {"completed": True, "updated_at": datetime.now(timezone.utc)}},
    )

    # Award EXP
    try:
        hunter = db["hunter"].find_one({"_id": ObjectId(payload.user_id)})
    except Exception:
        raise HTTPException(400, "Invalid user id")
    if not hunter:
        raise HTTPException(404, "Hunter not found")

    reward = int(quest.get("exp_reward", 50))
    new_exp = hunter.get("exp", 0) + reward
    level = hunter.get("level", 1)
    leveled_up = False
    while new_exp >= next_level_exp(level):
        new_exp -= next_level_exp(level)
        level += 1
        leveled_up = True

    db["hunter"].update_one(
        {"_id": hunter["_id"]},
        {"$set": {"exp": new_exp, "level": level, "updated_at": datetime.now(timezone.utc)}},
    )

    return {
        "message": "Quest completed",
        "reward": reward,
        "level": level,
        "exp": new_exp,
        "leveled_up": leveled_up,
    }


@app.get("/api/profile")
def get_profile(user_id: str):
    if db is None:
        raise HTTPException(500, "Database not configured")

    try:
        hunter = db["hunter"].find_one({"_id": ObjectId(user_id)})
    except Exception:
        raise HTTPException(400, "Invalid user id")
    if not hunter:
        raise HTTPException(404, "Hunter not found")

    # Compute progress to next level
    level = hunter.get("level", 1)
    exp = hunter.get("exp", 0)
    to_next = next_level_exp(level)
    progress = min(100, int(exp / to_next * 100)) if to_next else 0

    return {
        "id": str(hunter["_id"]),
        "name": hunter.get("name"),
        "title": hunter.get("title"),
        "level": level,
        "exp": exp,
        "exp_to_next": to_next,
        "progress_pct": progress,
        "streak": hunter.get("streak", 0),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
