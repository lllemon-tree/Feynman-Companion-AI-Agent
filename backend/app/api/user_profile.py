from fastapi import APIRouter, Depends
from sqlmodel import Session
from backend.app.core.database import get_session
from backend.app.api.dependencies import require_current_user, CurrentActor
from backend.app.models.user_profile import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
)
from backend.app.services.user_profile_service import UserProfileService

# 实例化 APIRouter 对象，统一配置 API 路由前缀为 /user/profile，并在 Swagger 文档中归类为 UserProfile
router = APIRouter(prefix="/user/profile", tags=["UserProfile"])


# 声明 HTTP GET 请求路由，路径为空字符串对应前缀 /user/profile，指定响应模型格式为字典
@router.get("", response_model=dict)
def get_user_profile(
    # 注入 require_current_user 依赖，自动校验 Bearer Token 并解析出当前登录用户信息[cite: 2]
    actor: CurrentActor = Depends(require_current_user),
    # 注入 get_session 依赖，为当前 API 请求分配并管理数据库会话上下文
    session: Session = Depends(get_session),
):
    """GET /api/v1/user/profile — 查询当前登录用户的学情信息[cite: 1, 3]"""
    # 调用 Service 层的查询方法，传入数据库 session 和当前用户的 user_id 获取学情对象[cite: 1, 3]
    profile_data = UserProfileService.get_profile_by_user_id(session, actor.user_id)
    # 按照项目前端约定的统一 JSON 结构返回数据（包含 code、msg、data 字段）[cite: 1, 3]
    return {
        "code": 200,                                 # 业务状态码 200 表示处理成功
        "msg": "success",                            # 成功提示文本
        "data": profile_data.model_dump(),           # 将 Pydantic/SQLModel 对象转换为字典返回
    }


# 声明 HTTP POST 请求路由，用于首次创建或全量覆盖学情档案
@router.post("", response_model=dict)
def create_user_profile(
    # 自动将前端发来的 JSON 请求体校验并解析为 UserProfileCreate 对象
    profile_in: UserProfileCreate,
    # 注入登录鉴权依赖，拦截未登录和游客请求[cite: 2]
    actor: CurrentActor = Depends(require_current_user),
    # 注入数据库会话依赖
    session: Session = Depends(get_session),
):
    """POST /api/v1/user/profile — 首次提交学情信息[cite: 1, 3]"""
    # 调用 Service 层的创建/更新服务，将提交的数据保存入库[cite: 1, 3]
    profile_data = UserProfileService.create_or_update_profile(
        session, actor.user_id, profile_in
    )
    # 返回保存成功响应结构[cite: 1, 3]
    return {
        "code": 200,                                 # 业务状态码 200
        "msg": "学情信息已保存",                       # 成功提示消息[cite: 1, 3]
        "data": profile_data.model_dump(),           # 序列化为字典的最新学情数据
    }


# 声明 HTTP PATCH 请求路由，用于更新学情档案中的部分字段
@router.patch("", response_model=dict)
def update_user_profile(
    # 自动将前端发来的 JSON 请求体校验并解析为 UserProfileUpdate 对象
    profile_in: UserProfileUpdate,
    # 注入登录鉴权依赖，确保仅当前用户能修改自己的学情[cite: 2]
    actor: CurrentActor = Depends(require_current_user),
    # 注入数据库会话依赖
    session: Session = Depends(get_session),
):
    """PATCH /api/v1/user/profile — 部分更新学情信息[cite: 1, 3]"""
    # 调用 Service 层的局部更新服务，只更新前端传了值的字段[cite: 1, 3]
    profile_data = UserProfileService.update_profile_partial(
        session, actor.user_id, profile_in
    )
    # 返回更新成功响应结构[cite: 1, 3]
    return {
        "code": 200,                                 # 业务状态码 200
        "msg": "学情信息已更新",                       # 成功提示消息[cite: 1, 3]
        "data": profile_data.model_dump(),           # 序列化为字典的更新后的学情数据
    }