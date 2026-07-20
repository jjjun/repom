from typing import Optional, List
from repom.examples.models.sample import SampleModel
from repom import BaseRepository, FilterParams
from repom.database import get_db_session


class SampleFilterParams(FilterParams):
    value: Optional[str] = None


class SampleRepository(BaseRepository[SampleModel]):
    def __init__(self, session=None):
        if session is None:
            session = get_db_session()
        super().__init__(SampleModel, session)

    def find(
        self,
        params: Optional[SampleFilterParams] = None,
        filters=None,
        include_deleted: bool = False,
        **kwargs
    ) -> List[SampleModel]:
        """
        Find SampleModel records based on the provided filters.

        Args:
            params (SampleFilterParams): Filtering conditions specified as a Pydantic model.

        **kwargs:
            offset (int): 取得するデータの開始位置
            limit (int): 取得するデータの件数
            order_by (Optional[Callable]): 結果を並べ替えるための呼び出し可能オブジェクト

        Returns:
            List[SampleModel]: A list of SampleModel records.
        """
        own_filters = []
        if params is not None and params.value is not None:
            own_filters.append(SampleModel.value == params.value)
        merged_filters = [*own_filters, *(filters or [])]
        return super().find(filters=merged_filters, include_deleted=include_deleted, **kwargs)
