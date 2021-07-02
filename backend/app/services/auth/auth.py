import uuid

from app.exceptions.auth import UserNotFound, KdOrgNotFound
from app.utils import generate_token
from app.views.main import get_app_config
from models.major import Major
from models.user import User
from pydantic import BaseModel, validator, constr


class AuthCompletionData(BaseModel):
    completion_id: uuid.UUID
    npm: constr(max_length=10,min_length=10)
    kd_org: str

    @validator("npm")
    def npm_must_be_numeric_only_and_minimum_10(cls, v: str):
        if not v.isnumeric():
            raise ValueError("npm must be numeric")
        return v


class AuthServices:
    @classmethod
    def process_sso_auth(cls, sso_profile) -> dict:
        user_name = sso_profile["username"]
        user = User.objects(username=user_name).first()
        if user is None:
            full_name = sso_profile['attributes']['ldap_cn']
            user = User(
                name=full_name,
                username=user_name
            )
            try:
                user_npm = sso_profile["attributes"]["npm"]
                major_name = sso_profile["attributes"]["study_program"]
                major_kd_org = sso_profile["attributes"]["kd_org"]
            except KeyError:
                completion_id = uuid.uuid4()
                user.completion_id = completion_id
                user.save()
                return {
                    'user_name':user_name,
                    'full_name':full_name,
                    'completion_id':str(completion_id)
                }
            user.npm = user_npm
            user.batch = f"20{user_npm[:2]}"
            major = Major.objects(kd_org=major_kd_org).first()
            if major is None:
                major = Major(name=major_name, kd_org=major_kd_org)
                major.save()

            user.major = major
            user.save()

        if user.completion_id is not None:
            return {
                'user_name': user.username,
                'full_name': user.name,
                'completion_id':str(user.completion_id)
            }

        token = generate_token(user.id, user.major.id)
        result = {
            "user_id": str(user.id),
            "major_id": str(user.major.id),
            "token": token
        }
        return result

    @classmethod
    def process_auth_completion(cls,data: AuthCompletionData) -> dict:
        user = User.objects(completion_id=data.completion_id).first()
        if user is None:
            raise UserNotFound()
        base_kd_org_data = get_app_config("BASE_KD_ORG")
        try:
            kd_org_data = base_kd_org_data[data.kd_org]
        except KeyError:
            raise KdOrgNotFound()

        major = Major.objects(kd_org=data.kd_org).first()
        if major is None:
            major = Major(name=kd_org_data["study_program"], kd_org=data.kd_org)
            major.save()

        user.npm = data.npm
        user.major = major
        user.completion_id = None
        user.batch = f"20{data.npm[:2]}"
        user.save()

        token = generate_token(user.id, user.major.id)
        result = {
            "user_id": str(user.id),
            "major_id": str(major.id),
            "token": token
        }
        return result






