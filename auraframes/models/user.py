from typing import Optional

from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    model_config = ConfigDict(extra='ignore')  # Ignore extra fields from API
    
    id: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    short_id: Optional[str] = None
    show_push_prompt: Optional[bool] = None
    latest_app_version: Optional[str] = None
    attribution_id: Optional[str] = None
    attribution_string: Optional[str] = None
    test_account: Optional[bool] = None
    avatar_file_name: Optional[str] = None
    has_frame: Optional[bool] = None
    analytics_optout: Optional[bool] = None
    admin_account: Optional[bool] = False
    auth_token: Optional[str] = None
