from typing import List, Optional

from sqlalchemy.orm import Session

from models.mapping_scene import MappingScene
from models.scene_rank import SceneRank
from schemas.scene_rank import SceneRankCreate, SceneRankResponse, SceneRankUpdate


class SceneRankService:
    def __init__(self, db: Session):
        self.db = db

    def list_ranks(self) -> List[SceneRankResponse]:
        ranks = self.db.query(SceneRank).order_by(SceneRank.updated_at.desc()).all()
        return [self._to_response(rank) for rank in ranks]

    def get_rank(self, rank_id: int) -> Optional[SceneRankResponse]:
        rank = self.db.query(SceneRank).filter(SceneRank.id == rank_id).first()
        return self._to_response(rank) if rank else None

    def create_rank(self, payload: SceneRankCreate) -> SceneRankResponse:
        self._validate_scene_ids(payload.scene_ids or [])
        rank = SceneRank(
            name=payload.name,
            orientation=payload.orientation,
            scene_ids=list(payload.scene_ids or []),
            gap_px=max(0, int(payload.gap_px or 0)),
            rank_metadata=payload.rank_metadata or {},
        )
        self.db.add(rank)
        self.db.commit()
        self.db.refresh(rank)
        return self._to_response(rank)

    def update_rank(self, rank_id: int, payload: SceneRankUpdate) -> Optional[SceneRankResponse]:
        rank = self.db.query(SceneRank).filter(SceneRank.id == rank_id).first()
        if not rank:
            return None

        data = payload.model_dump(exclude_unset=True)
        if "scene_ids" in data:
            self._validate_scene_ids(data["scene_ids"] or [])
            rank.scene_ids = list(data["scene_ids"] or [])
        if "name" in data:
            rank.name = data["name"]
        if "orientation" in data:
            rank.orientation = data["orientation"] or "horizontal"
        if "gap_px" in data:
            rank.gap_px = max(0, int(data["gap_px"] or 0))
        if "rank_metadata" in data:
            rank.rank_metadata = data["rank_metadata"] or {}

        self.db.commit()
        self.db.refresh(rank)
        return self._to_response(rank)

    def delete_rank(self, rank_id: int) -> bool:
        rank = self.db.query(SceneRank).filter(SceneRank.id == rank_id).first()
        if not rank:
            return False
        self.db.delete(rank)
        self.db.commit()
        return True

    def _validate_scene_ids(self, scene_ids: List[int]) -> None:
        if not scene_ids:
            return
        existing_ids = {
            scene_id
            for (scene_id,) in self.db.query(MappingScene.id).filter(MappingScene.id.in_(scene_ids)).all()
        }
        missing = [scene_id for scene_id in scene_ids if scene_id not in existing_ids]
        if missing:
            raise ValueError(f"Unknown mapping scene ids: {missing}")

    def _to_response(self, rank: SceneRank) -> SceneRankResponse:
        return SceneRankResponse(
            id=rank.id,
            name=rank.name,
            orientation=rank.orientation,
            scene_ids=list(rank.scene_ids or []),
            gap_px=int(rank.gap_px or 0),
            rank_metadata=rank.rank_metadata or {},
            created_at=rank.created_at,
            updated_at=rank.updated_at,
        )
