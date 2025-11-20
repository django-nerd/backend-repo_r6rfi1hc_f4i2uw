"""
Database Schemas for Solo Leveling Fitness App

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercase of the class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Hunter(BaseModel):
    """
    Collection: "hunter"
    Represents a user (Hunter) in the Solo Leveling inspired system
    """
    name: str = Field(..., description="Display name of the hunter")
    title: Optional[str] = Field(None, description="Optional title/rank nickname")
    level: int = Field(1, ge=1, description="Current level")
    exp: int = Field(0, ge=0, description="Current experience points")
    streak: int = Field(0, ge=0, description="Daily check-in streak")
    last_checkin: Optional[datetime] = Field(None, description="Last check-in timestamp")

class Workout(BaseModel):
    """
    Collection: "workout"
    A logged workout session awarding EXP
    """
    user_id: str = Field(..., description="Hunter user id (stringified ObjectId)")
    workout_type: str = Field(..., description="Type of workout, e.g., run, pushups, yoga")
    minutes: int = Field(..., ge=1, le=300, description="Duration in minutes")
    difficulty: str = Field("normal", description="easy | normal | hard")
    exp_awarded: int = Field(0, ge=0, description="Exp awarded for this workout")

class Quest(BaseModel):
    """
    Collection: "quest"
    Daily quest generated per user per day
    """
    user_id: str = Field(...)
    date: str = Field(..., description="YYYY-MM-DD for the quest day")
    title: str = Field(..., description="Quest title")
    description: Optional[str] = Field(None)
    exp_reward: int = Field(50, ge=0)
    completed: bool = Field(False)

class Checkin(BaseModel):
    """
    Collection: "checkin"
    Daily check-in records (for audit)
    """
    user_id: str = Field(...)
    date: str = Field(..., description="YYYY-MM-DD for the check-in day")
    streak_after: int = Field(..., ge=0)
