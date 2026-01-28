"""유효성 검증 유틸리티"""
from fastapi import HTTPException, status


class MapNameValidator:
    """맵 이름 검증 클래스"""

    REQUIRED_PREFIX = "smartfarm_"

    @classmethod
    def validate(cls, map_name: str) -> str:
        """맵 이름이 올바른 prefix를 가지고 있는지 검증

        Args:
            map_name: 검증할 맵 이름

        Returns:
            검증된 맵 이름

        Raises:
            HTTPException: prefix가 올바르지 않은 경우
        """
        if not map_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Map name is required"
            )

        if not map_name.startswith(cls.REQUIRED_PREFIX):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Map name must start with '{cls.REQUIRED_PREFIX}'. Got: '{map_name}'"
            )

        return map_name

    @classmethod
    def validate_silent(cls, map_name: str) -> bool:
        """맵 이름 검증 (예외 발생 없음)

        Args:
            map_name: 검증할 맵 이름

        Returns:
            유효하면 True, 아니면 False
        """
        if not map_name:
            return False

        return map_name.startswith(cls.REQUIRED_PREFIX)


def validate_map_name(map_name: str) -> str:
    """FastAPI dependency용 맵 이름 검증 함수

    Args:
        map_name: 검증할 맵 이름

    Returns:
        검증된 맵 이름

    Raises:
        HTTPException: prefix가 올바르지 않은 경우
    """
    return MapNameValidator.validate(map_name)
