from typing import Optional, Union, List, Callable
from sqlalchemy import select, desc, and_
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
        params: SampleFilterParams,
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
        filters = []
        if params.value is not None:
            filters.append(SampleModel.value == params.value)
        return super().find(filters=filters, **kwargs)
